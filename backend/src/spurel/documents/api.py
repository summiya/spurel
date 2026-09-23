"""FastAPI endpoints for document uploads."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from spurel.documents.chunk_inspector import (
    ChunkInspectionPersistenceError,
    ChunkInspectorService,
)
from spurel.documents.chunk_ports import DocumentChunkPersistenceError
from spurel.documents.chunking import DocumentChunkingError
from spurel.documents.dependencies import (
    get_chunk_inspector_service,
    get_document_service,
    get_document_upload_service,
)
from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    DocumentFilenameError,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)
from spurel.documents.ingestion_service import (
    DocumentIngestionError,
    DocumentNotFoundError,
)
from spurel.documents.parsing import DocumentParseError
from spurel.documents.ports import DocumentPersistenceError
from spurel.documents.processing import (
    DocumentProcessingService,
)
from spurel.documents.processing_dependencies import (
    get_document_processing_service,
)
from spurel.documents.schemas import (
    ChunkInspectionListResponse,
    ChunkInspectionResponse,
    DocumentListResponse,
    DocumentProcessingResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from spurel.documents.service import DocumentService
from spurel.embeddings.domain import EmbeddingError
from spurel.embeddings.pipeline import DocumentEmbeddingPipelineError
from spurel.embeddings.ports import ChunkEmbeddingPersistenceError
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

DocumentServiceDependency = Annotated[
    DocumentService,
    Depends(get_document_service),
]

ChunkInspectorServiceDependency = Annotated[
    ChunkInspectorService,
    Depends(get_chunk_inspector_service),
]

DocumentProcessingServiceDependency = Annotated[
    DocumentProcessingService,
    Depends(get_document_processing_service),
]

DocumentUploadServiceDependency = Annotated[
    DocumentUploadService,
    Depends(get_document_upload_service),
]


def _to_document_response(document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        filename=document.filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        created_at=document.created_at,
    )


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


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    knowledge_base_id: UUID,
    service: DocumentServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """List a bounded page of documents for one knowledge base."""
    try:
        documents = await service.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            offset=offset,
        )
    except DocumentPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document service temporarily unavailable",
        ) from exc

    return DocumentListResponse(
        items=[_to_document_response(document) for document in documents],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}/chunks",
    response_model=ChunkInspectionListResponse,
)
async def inspect_document_chunks(
    knowledge_base_id: UUID,
    document_id: UUID,
    service: ChunkInspectorServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChunkInspectionListResponse:
    """Inspect a bounded page of persisted chunks for one scoped document."""
    try:
        chunks = await service.list_by_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
    except ChunkInspectionPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="chunk inspector temporarily unavailable",
        ) from exc

    return ChunkInspectionListResponse(
        items=[
            ChunkInspectionResponse(
                id=item.id,
                document_id=item.document_id,
                index=item.index,
                text=item.text,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                has_embeddings=item.has_embeddings,
                embedding_count=item.embedding_count,
            )
            for item in chunks
        ],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessingResponse,
)
async def process_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    service: DocumentProcessingServiceDependency,
) -> DocumentProcessingResponse:
    """Parse, chunk, embed, and index one persisted document."""
    try:
        result = await service.process(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document was not found",
        ) from exc
    except (DocumentParseError, DocumentChunkingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document cannot be processed",
        ) from exc
    except (
        DocumentIngestionError,
        DocumentPersistenceError,
        DocumentChunkPersistenceError,
        ChunkEmbeddingPersistenceError,
        EmbeddingError,
        DocumentEmbeddingPipelineError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document processing service temporarily unavailable",
        ) from exc

    return DocumentProcessingResponse(
        document_id=result.document_id,
        knowledge_base_id=result.knowledge_base_id,
        chunk_count=result.chunk_count,
        embedded_chunk_count=result.embedded_chunk_count,
        embedding_provider=result.embedding_provider,
        embedding_model=result.embedding_model,
        embedding_dimensions=result.embedding_dimensions,
    )
