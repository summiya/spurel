"""Application-facing persistence ports for document chunks."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.documents.chunk_models import StagedDocumentChunkSet, StoredDocumentChunk
from spurel.documents.chunking import DocumentChunk


class DocumentChunkPersistenceError(RuntimeError):
    """Raised when document chunk persistence cannot complete."""


class DocumentProcessingConflictError(RuntimeError):
    """Raised when a live/reclaimed processing attempt cannot be continued."""


class DocumentChunkVersionIncompleteError(RuntimeError):
    """Raised when a staged version lacks complete matching embeddings."""


class DocumentChunkRepository(Protocol):
    """Persistence contract used by document chunk application services."""

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> StagedDocumentChunkSet:
        """Stage a new immutable chunk set without making it searchable."""
        ...

    async def promote_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Atomically activate only a complete embedded processing attempt."""
        ...

    async def fail_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Mark a failed attempt without replacing any active document version."""
        ...

    async def renew_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Refresh an active processing lease before the next embedding batch."""
        ...

    async def list_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunk]:
        """Return a bounded page ordered by chunk index."""
        ...


class StoredDocumentChunkReader(Protocol):
    """Read persisted chunks with stable database identities."""

    async def list_stored_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
        chunk_version: int | None = None,
    ) -> Sequence[StoredDocumentChunk]:
        """Return active chunks, or an explicit staged version for embedding."""
        ...
