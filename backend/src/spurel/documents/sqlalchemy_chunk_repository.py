"""SQLAlchemy repository adapter for document chunks."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.chunk_models import StoredDocumentChunk
from spurel.documents.chunk_ports import DocumentChunkPersistenceError
from spurel.documents.chunking import DocumentChunk


class SqlAlchemyDocumentChunkRepository:
    """Persist document chunks with isolated async SQLAlchemy sessions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        """Replace one document's chunks in a single transaction."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(
                        delete(DocumentChunkRecord).where(
                            DocumentChunkRecord.document_id == document_id
                        )
                    )
                    session.add_all(
                        [
                            DocumentChunkRecord.from_domain(
                                document_id=document_id,
                                chunk=chunk,
                            )
                            for chunk in chunks
                        ]
                    )
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError(
                "failed to replace document chunks"
            ) from exc

    async def list_stored_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[StoredDocumentChunk]:
        """Return persisted chunks with stable UUIDs in ordinal order."""
        statement = (
            select(DocumentChunkRecord)
            .where(DocumentChunkRecord.document_id == document_id)
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError(
                "failed to list stored document chunks"
            ) from exc

        return tuple(
            StoredDocumentChunk(
                id=record.id,
                document_id=record.document_id,
                chunk=record.to_domain(),
            )
            for record in records
        )

    async def list_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunk]:
        """Return a bounded chunk page in deterministic ordinal order."""
        statement = (
            select(DocumentChunkRecord)
            .where(DocumentChunkRecord.document_id == document_id)
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError(
                "failed to list document chunks"
            ) from exc

        return tuple(record.to_domain() for record in records)
