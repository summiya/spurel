"""SQLAlchemy repository adapter for chunk embeddings."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.persistence import ChunkEmbeddingRecord
from spurel.embeddings.ports import ChunkEmbeddingPersistenceError


class SqlAlchemyChunkEmbeddingRepository:
    """Persist chunk embeddings with isolated async SQLAlchemy sessions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_batch(
        self,
        embeddings: Sequence[ChunkEmbedding],
    ) -> None:
        """Upsert one embedding batch atomically by chunk and embedding space."""
        values = [
            {
                "id": ChunkEmbeddingRecord.from_domain(embedding).id,
                "chunk_id": embedding.chunk_id,
                "provider": embedding.provider,
                "model": embedding.model,
                "dimensions": embedding.dimensions,
                "embedding": list(embedding.vector.values),
                "created_at": embedding.created_at,
            }
            for embedding in embeddings
        ]

        statement = insert(ChunkEmbeddingRecord).values(values)
        statement = statement.on_conflict_do_update(
            constraint="uq_chunk_embeddings_chunk_space",
            set_={
                "embedding": statement.excluded.embedding,
                "created_at": statement.excluded.created_at,
            },
        )

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(statement)
        except SQLAlchemyError as exc:
            raise ChunkEmbeddingPersistenceError(
                "failed to persist chunk embeddings"
            ) from exc

    async def list_by_chunk(
        self,
        *,
        chunk_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkEmbedding]:
        """Return a bounded page of embeddings in deterministic space order."""
        statement = (
            select(ChunkEmbeddingRecord)
            .where(ChunkEmbeddingRecord.chunk_id == chunk_id)
            .order_by(
                ChunkEmbeddingRecord.provider.asc(),
                ChunkEmbeddingRecord.model.asc(),
                ChunkEmbeddingRecord.dimensions.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise ChunkEmbeddingPersistenceError(
                "failed to list chunk embeddings"
            ) from exc

        return tuple(record.to_domain() for record in records)
