"""Application-facing persistence ports for document chunks."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.documents.chunking import DocumentChunk


class DocumentChunkPersistenceError(RuntimeError):
    """Raised when document chunk persistence cannot complete."""


class DocumentChunkRepository(Protocol):
    """Persistence contract used by document chunk application services."""

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        """Atomically replace all chunks for one document."""
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
