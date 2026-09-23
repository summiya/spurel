"""SQLAlchemy exact cosine retrieval adapter."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.persistence import DocumentRecord
from spurel.embeddings.domain import EmbeddingVector
from spurel.embeddings.persistence import ChunkEmbeddingRecord
from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.ports import VectorRetrievalRepositoryError


class SqlAlchemyVectorRetrievalRepository:
    """Run exact cosine search over one knowledge base and embedding space."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

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
        """Return exact cosine-ranked chunks."""
        distance = ChunkEmbeddingRecord.embedding.cosine_distance(
            list(query_vector.values)
        ).label("cosine_distance")

        statement = (
            select(
                DocumentChunkRecord.id,
                DocumentChunkRecord.document_id,
                DocumentChunkRecord.chunk_index,
                DocumentChunkRecord.text,
                DocumentChunkRecord.start_offset,
                DocumentChunkRecord.end_offset,
                distance,
            )
            .join(
                ChunkEmbeddingRecord,
                ChunkEmbeddingRecord.chunk_id == DocumentChunkRecord.id,
            )
            .join(
                DocumentRecord,
                DocumentRecord.id == DocumentChunkRecord.document_id,
            )
            .where(
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                ChunkEmbeddingRecord.provider == provider,
                ChunkEmbeddingRecord.model == model,
                ChunkEmbeddingRecord.dimensions == dimensions,
            )
            .order_by(
                distance.asc(),
                DocumentChunkRecord.id.asc(),
            )
            .limit(limit)
        )

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise VectorRetrievalRepositoryError(
                "vector retrieval failed"
            ) from exc

        return tuple(
            VectorRetrievalMatch(
                chunk_id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                text=row.text,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                cosine_similarity=1.0 - float(row.cosine_distance),
            )
            for row in rows
        )
