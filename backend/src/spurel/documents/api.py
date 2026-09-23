"""FastAPI endpoints for document uploads."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from spurel.documents.dependencies import get_document_upload_service
from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    DocumentFilenameError,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)
from spurel.documents.ports import DocumentPersistenceError
from spurel.documents.schemas import DocumentUploadResponse
from spurel.documents.upload_service import (
    DocumentUploadError,
    DocumentUploadService,
    DocumentUploadSizeMismatchError,
)

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/documents",
    tags=["documents"],
)

_UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024

DocumentUploadServiceDependency = Annotated[
    DocumentUploadService,
    Depends(get_document_upload_service),
]


async def _upload_chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    """Yield bounded chunks from FastAPI's spooled upload file."""
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_SIZE_BYTES)
        if not chunk:
            return
        yield chunk


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: UUID,
    file: Annotated[UploadFile, File(description="PDF, Markdown, or plain text")],
    service: DocumentUploadServiceDependency,
) -> DocumentUploadResponse:
    """Upload one document into a knowledge base."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document filename is required",
        )

    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document media type is required",
        )

    if file.size is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document size is unavailable",
        )

    if file.size > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="document exceeds the maximum supported size",
        )

    try:
        result = await service.upload(
            knowledge_base_id=knowledge_base_id,
            filename=file.filename,
            media_type=file.content_type,
            declared_size_bytes=file.size,
            chunks=_upload_chunks(file),
        )
    except (
        DocumentFilenameError,
        DocumentSizeError,
        UnsupportedDocumentMediaTypeError,
        DocumentUploadSizeMismatchError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document upload is invalid",
        ) from exc
    except (DocumentPersistenceError, DocumentUploadError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document upload service temporarily unavailable",
        ) from exc
    finally:
        await file.close()

    document = result.document
    return DocumentUploadResponse(
        id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        filename=document.filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        created_at=document.created_at,
        sha256=result.sha256,
    )
