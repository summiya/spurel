"""Read-only SQLAlchemy adapter for immutable document chunk-set history."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_inspector import ChunkInspectionItem
from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.chunk_versions_persistence import DocumentChunkVersionRecord
from spurel.documents.persistence import DocumentRecord
from spurel.documents.versions import (
    DocumentChunkVersion,
    DocumentVersionPersistenceError,
)
from spurel.embeddings.persistence import ChunkEmbeddingRecord


class SqlAlchemyDocumentVersionRepository:
    """Keep past chunk identities queryable without exposing other knowledge bases."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_versions(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunkVersion] | None:
        """List version numbers and metadata, newest first."""
        statement = (
            select(DocumentChunkVersionRecord, DocumentRecord.active_chunk_version)
            .join(DocumentRecord, DocumentRecord.id == DocumentChunkVersionRecord.document_id)
            .where(
                DocumentRecord.id == document_id,
                DocumentRecord.knowledge_base_id == knowledge_base_id,
            )
            .order_by(DocumentChunkVersionRecord.version.desc())
            .limit(limit)
            .offset(offset)
        )
        try:
            async with self._session_factory() as session:
                if not await self._document_exists(
                    session, knowledge_base_id=knowledge_base_id, document_id=document_id
                ):
                    return None
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise DocumentVersionPersistenceError("failed to list document versions") from exc

        return tuple(
            DocumentChunkVersion(
                version=version.version,
                chunk_count=version.chunk_count,
                created_at=version.created_at,
                is_active=version.version == active_version,
            )
            for version, active_version in rows
        )

    async def list_version_chunks(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        version: int,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem] | None:
        """Inspect one scoped version including saved embedding availability."""
        embedding_count = (
            select(func.count(ChunkEmbeddingRecord.id))
            .where(ChunkEmbeddingRecord.chunk_id == DocumentChunkRecord.id)
            .correlate(DocumentChunkRecord)
            .scalar_subquery()
            .label("embedding_count")
        )
        statement = (
            select(
                DocumentChunkRecord.id,
                DocumentChunkRecord.document_id,
                DocumentChunkRecord.chunk_index,
                DocumentChunkRecord.text,
                DocumentChunkRecord.start_offset,
                DocumentChunkRecord.end_offset,
                embedding_count,
            )
            .where(
                DocumentChunkRecord.document_id == document_id,
                DocumentChunkRecord.chunk_version == version,
            )
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )
        version_statement = (
            select(DocumentChunkVersionRecord.version)
            .join(DocumentRecord, DocumentRecord.id == DocumentChunkVersionRecord.document_id)
            .where(
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                DocumentRecord.id == document_id,
                DocumentChunkVersionRecord.version == version,
            )
        )
        try:
            async with self._session_factory() as session:
                if await session.scalar(version_statement) is None:
                    return None
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise DocumentVersionPersistenceError("failed to inspect document version") from exc

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

    @staticmethod
    async def _document_exists(
        session: AsyncSession,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> bool:
        statement = select(DocumentRecord.id).where(
            DocumentRecord.id == document_id,
            DocumentRecord.knowledge_base_id == knowledge_base_id,
        )
        return await session.scalar(statement) is not None
