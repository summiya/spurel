"""SQLAlchemy repository adapter for document chunks."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_models import StoredDocumentChunk
from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.chunk_ports import DocumentChunkPersistenceError
from spurel.documents.chunk_versions_persistence import DocumentChunkVersionRecord
from spurel.documents.chunking import DocumentChunk
from spurel.documents.persistence import DocumentRecord


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
        """Append changed chunk sets, retaining historical IDs and embeddings.

        Acquiring the document row lock serializes concurrent reprocessing.
        Unchanged active chunk sets retain their UUIDs; new sets receive a new
        monotonically increasing version. Activation is atomic with insertion.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    document = await session.scalar(
                        select(DocumentRecord)
                        .where(DocumentRecord.id == document_id)
                        .with_for_update()
                    )
                    if document is None:
                        raise DocumentChunkPersistenceError("document was not found")

                    active_version = document.active_chunk_version
                    if active_version:
                        current = (
                            await session.scalars(
                                select(DocumentChunkRecord)
                                .where(
                                    DocumentChunkRecord.document_id == document_id,
                                    DocumentChunkRecord.chunk_version == active_version,
                                )
                                .order_by(DocumentChunkRecord.chunk_index.asc())
                            )
                        ).all()
                        if len(current) == len(chunks) and all(
                            row.to_domain() == chunk
                            for row, chunk in zip(current, chunks, strict=True)
                        ):
                            return

                    latest = await session.scalar(
                        select(func.max(DocumentChunkVersionRecord.version)).where(
                            DocumentChunkVersionRecord.document_id == document_id
                        )
                    )
                    next_version = (latest or 0) + 1
                    session.add(
                        DocumentChunkVersionRecord(
                            document_id=document_id,
                            version=next_version,
                            chunk_count=len(chunks),
                            created_at=datetime.now(UTC),
                        )
                    )
                    # The chunk rows reference (document_id, version) by FK.
                    await session.flush()
                    session.add_all(
                        [
                            DocumentChunkRecord.from_domain(
                                document_id=document_id,
                                chunk=chunk,
                                chunk_version=next_version,
                            )
                            for chunk in chunks
                        ]
                    )
                    document.active_chunk_version = next_version
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to version document chunks") from exc

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
            .join(DocumentRecord, DocumentRecord.id == DocumentChunkRecord.document_id)
            .where(
                DocumentChunkRecord.document_id == document_id,
                DocumentChunkRecord.chunk_version == DocumentRecord.active_chunk_version,
            )
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to list stored document chunks") from exc

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
            .join(DocumentRecord, DocumentRecord.id == DocumentChunkRecord.document_id)
            .where(
                DocumentChunkRecord.document_id == document_id,
                DocumentChunkRecord.chunk_version == DocumentRecord.active_chunk_version,
            )
            .order_by(DocumentChunkRecord.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to list document chunks") from exc

        return tuple(record.to_domain() for record in records)
