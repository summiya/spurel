"""Document upload orchestration independent of HTTP and storage providers."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from dataclasses import dataclass
from uuid import UUID

from spurel.documents.domain import MAX_DOCUMENT_SIZE_BYTES, Document
from spurel.documents.ports import DocumentPersistenceError, DocumentRepository
from spurel.documents.storage import DocumentBlobStorage, DocumentStorageError


class DocumentUploadError(RuntimeError):
    """Base error for document upload orchestration."""


class DocumentUploadSizeMismatchError(DocumentUploadError):
    """Raised when streamed content does not match the declared size."""


class DocumentUploadCleanupError(DocumentUploadError):
    """Raised when compensating blob cleanup cannot complete."""


@dataclass(frozen=True, slots=True)
class DocumentUploadResult:
    """Result of a successfully stored and registered document."""

    document: Document
    object_key: str
    sha256: str


class DocumentUploadService:
    """Stream document bytes to blob storage and persist validated metadata."""

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentBlobStorage,
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def upload(
        self,
        *,
        knowledge_base_id: UUID,
        filename: str,
        media_type: str,
        declared_size_bytes: int,
        chunks: AsyncIterable[bytes],
    ) -> DocumentUploadResult:
        """Store content and persist its document metadata."""
        document = Document.create(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            media_type=media_type,
            size_bytes=declared_size_bytes,
        )
        object_key = _object_key_for(document)

        digest = hashlib.sha256()
        actual_size_bytes = 0

        async def validated_chunks() -> AsyncIterable[bytes]:
            nonlocal actual_size_bytes

            async for chunk in chunks:
                if not chunk:
                    continue

                actual_size_bytes += len(chunk)
                if actual_size_bytes > MAX_DOCUMENT_SIZE_BYTES:
                    raise DocumentUploadSizeMismatchError(
                        "streamed document exceeds the maximum supported size"
                    )

                digest.update(chunk)
                yield chunk

        try:
            await self._storage.put(
                object_key=object_key,
                chunks=validated_chunks(),
            )
        except DocumentUploadSizeMismatchError:
            await self._cleanup_or_raise(object_key)
            raise
        except DocumentStorageError as exc:
            raise DocumentUploadError("failed to store document content") from exc

        if actual_size_bytes != declared_size_bytes:
            await self._cleanup_or_raise(object_key)
            raise DocumentUploadSizeMismatchError(
                "streamed document size does not match the declared size"
            )

        try:
            await self._repository.add(document)
        except DocumentPersistenceError:
            await self._cleanup_or_raise(object_key)
            raise

        return DocumentUploadResult(
            document=document,
            object_key=object_key,
            sha256=digest.hexdigest(),
        )

    async def _cleanup_or_raise(self, object_key: str) -> None:
        try:
            await self._storage.delete(object_key=object_key)
        except DocumentStorageError as exc:
            raise DocumentUploadCleanupError(
                "failed to clean up document content after upload failure"
            ) from exc


def _object_key_for(document: Document) -> str:
    """Build an opaque server-controlled storage key without using filenames."""
    return (
        f"knowledge-bases/{document.knowledge_base_id}/"
        f"documents/{document.id}"
    )
