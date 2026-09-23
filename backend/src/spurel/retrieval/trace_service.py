"""Application service for retrieval trace persistence and history."""

from collections.abc import Sequence
from uuid import UUID

from spurel.retrieval.trace_ports import RetrievalTraceRepository
from spurel.retrieval.tracing import RetrievalTrace, RetrievalTraceSummary

MAX_RETRIEVAL_TRACE_PAGE_SIZE = 100


class RetrievalTraceQueryError(ValueError):
    """Raised when retrieval trace history parameters are invalid."""


class RetrievalTraceNotFoundError(LookupError):
    """Raised when a scoped retrieval trace does not exist."""


class RetrievalTraceService:
    """Persist and browse completed retrieval runs."""

    def __init__(self, repository: RetrievalTraceRepository) -> None:
        self._repository = repository

    async def record(self, trace: RetrievalTrace) -> None:
        """Persist one completed trace atomically."""
        await self._repository.add(trace)

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[RetrievalTraceSummary]:
        """Return a bounded newest-first trace history page."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_RETRIEVAL_TRACE_PAGE_SIZE
        ):
            raise RetrievalTraceQueryError(
                "retrieval trace page limit is outside the supported range"
            )

        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise RetrievalTraceQueryError(
                "retrieval trace page offset is invalid"
            )

        return await self._repository.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace:
        """Return one trace only when it belongs to the requested knowledge base."""
        trace = await self._repository.get_by_id(
            knowledge_base_id=knowledge_base_id,
            trace_id=trace_id,
        )
        if trace is None:
            raise RetrievalTraceNotFoundError("retrieval trace was not found")
        return trace
