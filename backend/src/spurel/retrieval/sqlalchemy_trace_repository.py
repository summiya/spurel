"""SQLAlchemy repository adapter for retrieval traces."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.retrieval.trace_persistence import (
    RetrievalTraceRecord,
    RetrievalTraceResultRecord,
)
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceSummary,
)


class SqlAlchemyRetrievalTraceRepository:
    """Persist and read retrieval traces and ranked snapshots."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, trace: RetrievalTrace) -> None:
        """Persist one completed retrieval trace in a single transaction."""
        trace_record = RetrievalTraceRecord.from_domain(trace)
        result_records = [
            RetrievalTraceResultRecord.from_domain(
                trace_id=trace.id,
                result=result,
            )
            for result in trace.results
        ]

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(trace_record)
                    session.add_all(result_records)
        except SQLAlchemyError as exc:
            raise RetrievalTracePersistenceError(
                "failed to persist retrieval trace"
            ) from exc

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[RetrievalTraceSummary]:
        """Return newest traces without loading result snapshot text."""
        result_count = (
            select(func.count(RetrievalTraceResultRecord.id))
            .where(
                RetrievalTraceResultRecord.trace_id == RetrievalTraceRecord.id
            )
            .correlate(RetrievalTraceRecord)
            .scalar_subquery()
            .label("result_count")
        )

        statement = (
            select(
                RetrievalTraceRecord,
                result_count,
            )
            .where(
                RetrievalTraceRecord.knowledge_base_id == knowledge_base_id
            )
            .order_by(
                RetrievalTraceRecord.created_at.desc(),
                RetrievalTraceRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise RetrievalTracePersistenceError(
                "failed to list retrieval traces"
            ) from exc

        return tuple(
            _to_summary(record=record, result_count=result_count)
            for record, result_count in rows
        )

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace | None:
        """Return one knowledge-base-scoped trace with ranked result snapshots."""
        trace_statement = select(RetrievalTraceRecord).where(
            RetrievalTraceRecord.knowledge_base_id == knowledge_base_id,
            RetrievalTraceRecord.id == trace_id,
        )
        result_statement = (
            select(RetrievalTraceResultRecord)
            .where(RetrievalTraceResultRecord.trace_id == trace_id)
            .order_by(RetrievalTraceResultRecord.rank.asc())
        )

        try:
            async with self._session_factory() as session:
                record = (
                    await session.execute(trace_statement)
                ).scalar_one_or_none()
                if record is None:
                    return None

                result_records = (
                    await session.execute(result_statement)
                ).scalars().all()
        except SQLAlchemyError as exc:
            raise RetrievalTracePersistenceError(
                "failed to load retrieval trace"
            ) from exc

        return RetrievalTrace(
            id=record.id,
            knowledge_base_id=record.knowledge_base_id,
            mode=RetrievalTraceMode(record.mode),
            query=record.query,
            top_k=record.top_k,
            candidate_k=record.candidate_k,
            rrf_k=record.rrf_k,
            duration_ms=record.duration_ms,
            embedding_provider=record.embedding_provider,
            embedding_model=record.embedding_model,
            embedding_dimensions=record.embedding_dimensions,
            results=tuple(
                result_record.to_domain()
                for result_record in result_records
            ),
            created_at=record.created_at,
        )


def _to_summary(
    *,
    record: RetrievalTraceRecord,
    result_count: int,
) -> RetrievalTraceSummary:
    return RetrievalTraceSummary(
        id=record.id,
        knowledge_base_id=record.knowledge_base_id,
        mode=RetrievalTraceMode(record.mode),
        query=record.query,
        top_k=record.top_k,
        candidate_k=record.candidate_k,
        rrf_k=record.rrf_k,
        duration_ms=record.duration_ms,
        embedding_provider=record.embedding_provider,
        embedding_model=record.embedding_model,
        embedding_dimensions=record.embedding_dimensions,
        result_count=int(result_count),
        created_at=record.created_at,
    )
