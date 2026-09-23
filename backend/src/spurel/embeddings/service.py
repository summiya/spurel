"""Application services for persisted chunk embeddings."""

from collections.abc import Sequence
from uuid import UUID

from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import MAX_EMBEDDING_BATCH_SIZE
from spurel.embeddings.ports import ChunkEmbeddingRepository

MAX_EMBEDDINGS_PER_CHUNK_PAGE = 100


class ChunkEmbeddingBatchError(ValueError):
    """Raised when an embedding persistence batch is invalid."""


class ChunkEmbeddingService:
    """Coordinate chunk embedding persistence through an abstract repository."""

    def __init__(self, repository: ChunkEmbeddingRepository) -> None:
        self._repository = repository

    async def upsert_batch(
        self,
        embeddings: Sequence[ChunkEmbedding],
    ) -> None:
        """Validate and atomically upsert one embedding-space batch."""
        _validate_batch(embeddings)
        await self._repository.upsert_batch(embeddings)

    async def list_by_chunk(
        self,
        *,
        chunk_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkEmbedding]:
        """List a bounded page of embeddings for one chunk."""
        if limit < 1 or limit > MAX_EMBEDDINGS_PER_CHUNK_PAGE:
            raise ChunkEmbeddingBatchError(
                "embedding page limit is outside the supported range"
            )
        if offset < 0:
            raise ChunkEmbeddingBatchError(
                "embedding page offset must not be negative"
            )

        return await self._repository.list_by_chunk(
            chunk_id=chunk_id,
            limit=limit,
            offset=offset,
        )


def _validate_batch(embeddings: Sequence[ChunkEmbedding]) -> None:
    if not embeddings or len(embeddings) > MAX_EMBEDDING_BATCH_SIZE:
        raise ChunkEmbeddingBatchError(
            "embedding persistence batch size is outside the supported range"
        )

    first = embeddings[0]
    expected_space = (
        first.provider,
        first.model,
        first.dimensions,
    )

    seen_chunk_ids: set[UUID] = set()

    for embedding in embeddings:
        current_space = (
            embedding.provider,
            embedding.model,
            embedding.dimensions,
        )
        if current_space != expected_space:
            raise ChunkEmbeddingBatchError(
                "embedding batch must belong to one embedding space"
            )

        if embedding.chunk_id in seen_chunk_ids:
            raise ChunkEmbeddingBatchError(
                "embedding batch contains duplicate chunk IDs"
            )

        seen_chunk_ids.add(embedding.chunk_id)
