"""SQLAlchemy repository adapter for the Chunk Inspector."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_inspector import (
    ChunkInspectionItem,
    ChunkInspectionPersistenceError,
)
from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.persistence import DocumentRecord
from spurel.embeddings.persistence import ChunkEmbeddingRecord


class SqlAlchemyChunkInspectorRepository:
    """Inspect persisted chunks and embedding availability safely."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_by_document(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem]:
        """Return a bounded scoped chunk page with embedding counts."""
        embedding_counts = (
            select(
                ChunkEmbeddingRecord.chunk_id.label("chunk_id"),
                func.count(ChunkEmbeddingRecord.id).label("embedding_count"),
            )
            .group_by(ChunkEmbeddingRecord.chunk_id)
            .subquery()
        )

        statement = (
            select(
                DocumentChunkRecord.id,
                DocumentChunkRecord.document_id,
                DocumentChunkRecord.chunk_index,
                DocumentChunkRecord.text,
                DocumentChunkRecord.start_offset,
                DocumentChunkRecord.end_offset,
                func.coalesce(embedding_counts.c.embedding_count, 0).label(
                    "embedding_count"
                ),
            )
            .join(
                DocumentRecord,
                DocumentRecord.id == DocumentChunkRecord.document_id,
            )
            .outerjoin(
                embedding_counts,
                embedding_counts.c.chunk_id == DocumentChunkRecord.id,
            )
            .where(
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                DocumentChunkRecord.document_id == document_id,
            )
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise ChunkInspectionPersistenceError(
                "failed to inspect document chunks"
            ) from exc

        return tuple(
            ChunkInspectionItem(
                id=row.id,
                document_id=row.document_id,
                index=row.chunk_index,
                text=row.text,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                embedding_count=int(row.embedding_count),
            )
            for row in rows
        )
