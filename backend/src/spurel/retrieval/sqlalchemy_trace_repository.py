"""SQLAlchemy repository adapter for retrieval traces."""

from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.retrieval.trace_persistence import (
    RetrievalTraceRecord,
    RetrievalTraceResultRecord,
)
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.tracing import RetrievalTrace


class SqlAlchemyRetrievalTraceRepository:
    """Persist retrieval traces and ranked snapshots atomically."""

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
