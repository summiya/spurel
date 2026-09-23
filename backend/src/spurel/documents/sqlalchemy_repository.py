"""SQLAlchemy repository adapter for documents."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.domain import Document
from spurel.documents.persistence import DocumentRecord
from spurel.documents.ports import DocumentPersistenceError


class SqlAlchemyDocumentRepository:
    """Persist document metadata with isolated async SQLAlchemy sessions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, document: Document) -> None:
        """Persist one document in its own transaction."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(DocumentRecord.from_domain(document))
        except SQLAlchemyError as exc:
            raise DocumentPersistenceError("failed to persist document") from exc

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        """Return one document scoped to its knowledge base."""
        statement = select(DocumentRecord).where(
            DocumentRecord.id == document_id,
            DocumentRecord.knowledge_base_id == knowledge_base_id,
        )

        try:
            async with self._session_factory() as session:
                record = await session.scalar(statement)
        except SQLAlchemyError as exc:
            raise DocumentPersistenceError("failed to load document") from exc

        return record.to_domain() if record is not None else None

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        """Return a bounded document page in deterministic order."""
        statement = (
            select(DocumentRecord)
            .where(DocumentRecord.knowledge_base_id == knowledge_base_id)
            .order_by(
                DocumentRecord.created_at.asc(),
                DocumentRecord.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise DocumentPersistenceError("failed to list documents") from exc

        return tuple(record.to_domain() for record in records)
