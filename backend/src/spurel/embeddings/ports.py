"""Application-facing persistence ports for chunk embeddings."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.embeddings.chunk import ChunkEmbedding


class ChunkEmbeddingPersistenceError(RuntimeError):
    """Raised when chunk embedding persistence cannot complete."""


class ChunkEmbeddingRepository(Protocol):
    """Persistence contract used by embedding application services."""

    async def upsert_batch(
        self,
        embeddings: Sequence[ChunkEmbedding],
    ) -> None:
        """Atomically insert or update one homogeneous embedding batch."""
        ...

    async def list_by_chunk(
        self,
        *,
        chunk_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkEmbedding]:
        """Return a bounded page of embeddings for one chunk."""
        ...
