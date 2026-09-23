"""Application-facing persistence port for vector retrieval."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.embeddings.domain import EmbeddingVector
from spurel.retrieval.domain import VectorRetrievalMatch


class VectorRetrievalRepositoryError(RuntimeError):
    """Raised when vector retrieval persistence cannot complete."""


class VectorRetrievalRepository(Protocol):
    """Search persisted chunk embeddings within one explicit embedding space."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query_vector: EmbeddingVector,
        provider: str,
        model: str,
        dimensions: int,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        """Return the nearest chunks ordered by cosine similarity."""
        ...
