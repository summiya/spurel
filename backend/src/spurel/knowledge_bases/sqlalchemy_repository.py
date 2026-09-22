"""SQLAlchemy repository adapter for knowledge bases."""

from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.knowledge_bases.domain import KnowledgeBase
from spurel.knowledge_bases.persistence import KnowledgeBaseRecord
from spurel.knowledge_bases.ports import KnowledgeBasePersistenceError


class SqlAlchemyKnowledgeBaseRepository:
    """Persist knowledge bases with isolated async SQLAlchemy sessions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, knowledge_base: KnowledgeBase) -> None:
        """Persist one knowledge base in its own transaction."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(KnowledgeBaseRecord.from_domain(knowledge_base))
        except SQLAlchemyError as exc:
            raise KnowledgeBasePersistenceError(
                "failed to persist knowledge base"
            ) from exc

    async def list(self) -> Sequence[KnowledgeBase]:
        """Return all knowledge bases in deterministic creation order."""
        statement = select(KnowledgeBaseRecord).order_by(
            KnowledgeBaseRecord.created_at.asc(),
            KnowledgeBaseRecord.id.asc(),
        )

        try:
            async with self._session_factory() as session:
                result = await session.scalars(statement)
                records = result.all()
        except SQLAlchemyError as exc:
            raise KnowledgeBasePersistenceError(
                "failed to list knowledge bases"
            ) from exc

        return tuple(record.to_domain() for record in records)
