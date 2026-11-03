"""SQLAlchemy adapter for staged, immutable document chunk versions."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_models import StagedDocumentChunkSet, StoredDocumentChunk
from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.chunk_ports import (
    DocumentChunkPersistenceError,
    DocumentChunkVersionIncompleteError,
    DocumentProcessingConflictError,
)
from spurel.documents.chunk_versions_persistence import DocumentChunkVersionRecord
from spurel.documents.chunking import DocumentChunk
from spurel.documents.persistence import DocumentRecord
from spurel.embeddings.persistence import ChunkEmbeddingRecord

# Recovery from a terminated request is possible once this lease expires.
# Each embedding batch renews the lease; activation uses a fenced attempt UUID.
_PROCESSING_LEASE = timedelta(minutes=30)


class SqlAlchemyDocumentChunkRepository:
    """Persist immutable chunk sets and promote only fully indexed versions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> StagedDocumentChunkSet:
        """Reserve a staged version while keeping the previous one searchable.

        Only one non-expired processing attempt can own a document at a time.
        Retrying a failed/expired attempt with identical chunks reuses its UUIDs.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    document = await _lock_document(session, document_id)
                    now = datetime.now(UTC)

                    in_progress = await session.scalar(
                        select(DocumentChunkVersionRecord)
                        .where(
                            DocumentChunkVersionRecord.document_id == document_id,
                            DocumentChunkVersionRecord.status == "processing",
                        )
                    )
                    if in_progress is not None:
                        if in_progress.lease_expires_at > now:
                            raise DocumentProcessingConflictError(
                                "document processing is already in progress"
                            )
                        # A crashed process has lost its lease. Its attempt ID
                        # cannot promote after a later attempt reclaims the row.
                        in_progress.status = "failed"
                        in_progress.attempt_id = None
                        in_progress.lease_expires_at = None
                        await session.flush()

                    active_version = document.active_chunk_version
                    if active_version and await _chunks_match(
                        session,
                        document_id=document_id,
                        version=active_version,
                        chunks=chunks,
                    ):
                        return StagedDocumentChunkSet(
                            version=active_version,
                            attempt_id=None,
                            reused_active=True,
                        )

                    latest = await session.scalar(
                        select(DocumentChunkVersionRecord)
                        .where(DocumentChunkVersionRecord.document_id == document_id)
                        .order_by(DocumentChunkVersionRecord.version.desc())
                        .limit(1)
                    )
                    attempt_id = uuid4()
                    lease_expires_at = now + _PROCESSING_LEASE
                    if (
                        latest is not None
                        and latest.status == "failed"
                        and await _chunks_match(
                            session,
                            document_id=document_id,
                            version=latest.version,
                            chunks=chunks,
                        )
                    ):
                        latest.status = "processing"
                        latest.attempt_id = attempt_id
                        latest.lease_expires_at = lease_expires_at
                        latest.attempt_count += 1
                        version = latest.version
                    else:
                        version = (latest.version if latest is not None else 0) + 1
                        session.add(
                            DocumentChunkVersionRecord(
                                document_id=document_id,
                                version=version,
                                chunk_count=len(chunks),
                                created_at=now,
                                status="processing",
                                attempt_id=attempt_id,
                                lease_expires_at=lease_expires_at,
                                attempt_count=1,
                            )
                        )
                        await session.flush()
                        session.add_all(
                            [
                                DocumentChunkRecord.from_domain(
                                    document_id=document_id,
                                    chunk=chunk,
                                    chunk_version=version,
                                )
                                for chunk in chunks
                            ]
                        )

                    return StagedDocumentChunkSet(
                        version=version,
                        attempt_id=attempt_id,
                        reused_active=False,
                    )
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to stage document chunks") from exc

    async def renew_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Refresh a processing lease only while the caller owns the attempt."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await _lock_document(session, document_id)
                    staged = await _get_processing_version(
                        session,
                        document_id=document_id,
                        version=version,
                        attempt_id=attempt_id,
                    )
                    staged.lease_expires_at = datetime.now(UTC) + _PROCESSING_LEASE
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to renew processing lease") from exc

    async def promote_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Switch active version only when every staged chunk has an embedding."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    document = await _lock_document(session, document_id)
                    staged = await _get_processing_version(
                        session,
                        document_id=document_id,
                        version=version,
                        attempt_id=attempt_id,
                    )

                    total_chunks = await session.scalar(
                        select(func.count(DocumentChunkRecord.id)).where(
                            DocumentChunkRecord.document_id == document_id,
                            DocumentChunkRecord.chunk_version == version,
                        )
                    )
                    embedded_chunks = await session.scalar(
                        select(func.count(ChunkEmbeddingRecord.chunk_id))
                        .join(
                            DocumentChunkRecord,
                            DocumentChunkRecord.id == ChunkEmbeddingRecord.chunk_id,
                        )
                        .where(
                            DocumentChunkRecord.document_id == document_id,
                            DocumentChunkRecord.chunk_version == version,
                            ChunkEmbeddingRecord.provider == provider,
                            ChunkEmbeddingRecord.model == model,
                            ChunkEmbeddingRecord.dimensions == dimensions,
                        )
                    )
                    if (
                        total_chunks != staged.chunk_count
                        or embedded_chunks != staged.chunk_count
                    ):
                        raise DocumentChunkVersionIncompleteError(
                            "staged document version has incomplete embeddings"
                        )

                    # The document row lock serializes publication with any new
                    # staging/recovery attempt. Version + attempt is a fencing key.
                    document.active_chunk_version = version
                    staged.status = "ready"
                    staged.attempt_id = None
                    staged.lease_expires_at = None
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to promote document version") from exc

    async def fail_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Preserve the old active version and mark only our attempt failed."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await _lock_document(session, document_id)
                    staged = await session.scalar(
                        select(DocumentChunkVersionRecord).where(
                            DocumentChunkVersionRecord.document_id == document_id,
                            DocumentChunkVersionRecord.version == version,
                        )
                    )
                    if (
                        staged is not None
                        and staged.status == "processing"
                        and staged.attempt_id == attempt_id
                    ):
                        staged.status = "failed"
                        staged.attempt_id = None
                        staged.lease_expires_at = None
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to mark document version") from exc

    async def list_stored_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
        chunk_version: int | None = None,
    ) -> Sequence[StoredDocumentChunk]:
        """Read an explicit staging version or the active one by default."""
        statement = _chunks_for_document(
            document_id=document_id,
            chunk_version=chunk_version,
        ).limit(limit).offset(offset)
        try:
            async with self._session_factory() as session:
                records = (await session.scalars(statement)).all()
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
        """List the active document chunk set in source order."""
        statement = _chunks_for_document(
            document_id=document_id, chunk_version=None
        ).limit(limit).offset(offset)
        try:
            async with self._session_factory() as session:
                records = (await session.scalars(statement)).all()
        except SQLAlchemyError as exc:
            raise DocumentChunkPersistenceError("failed to list document chunks") from exc
        return tuple(record.to_domain() for record in records)


def _chunks_for_document(*, document_id: UUID, chunk_version: int | None):
    """Build one indexed or staged chunk query without changing default reads."""
    statement = (
        select(DocumentChunkRecord)
        .join(DocumentRecord, DocumentRecord.id == DocumentChunkRecord.document_id)
        .where(DocumentChunkRecord.document_id == document_id)
    )
    if chunk_version is None:
        statement = statement.where(
            DocumentChunkRecord.chunk_version == DocumentRecord.active_chunk_version
        )
    else:
        statement = statement.where(DocumentChunkRecord.chunk_version == chunk_version)
    return statement.order_by(DocumentChunkRecord.chunk_index.asc())


async def _lock_document(session: AsyncSession, document_id: UUID) -> DocumentRecord:
    document = await session.scalar(
        select(DocumentRecord).where(DocumentRecord.id == document_id).with_for_update()
    )
    if document is None:
        raise DocumentChunkPersistenceError("document was not found")
    return document


async def _chunks_match(
    session: AsyncSession,
    *,
    document_id: UUID,
    version: int,
    chunks: Sequence[DocumentChunk],
) -> bool:
    records = (
        await session.scalars(
            select(DocumentChunkRecord)
            .where(
                DocumentChunkRecord.document_id == document_id,
                DocumentChunkRecord.chunk_version == version,
            )
            .order_by(DocumentChunkRecord.chunk_index.asc())
        )
    ).all()
    return len(records) == len(chunks) and all(
        record.to_domain() == chunk
        for record, chunk in zip(records, chunks, strict=True)
    )


async def _get_processing_version(
    session: AsyncSession,
    *,
    document_id: UUID,
    version: int,
    attempt_id: UUID,
) -> DocumentChunkVersionRecord:
    staged = await session.scalar(
        select(DocumentChunkVersionRecord).where(
            DocumentChunkVersionRecord.document_id == document_id,
            DocumentChunkVersionRecord.version == version,
        )
    )
    if (
        staged is None
        or staged.status != "processing"
        or staged.attempt_id != attempt_id
    ):
        raise DocumentProcessingConflictError("processing attempt was superseded")
    return staged
