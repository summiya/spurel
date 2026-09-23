"""Application service for retrieval trace persistence."""

from spurel.retrieval.trace_ports import RetrievalTraceRepository
from spurel.retrieval.tracing import RetrievalTrace


class RetrievalTraceService:
    """Persist completed retrieval runs through an abstract repository."""

    def __init__(self, repository: RetrievalTraceRepository) -> None:
        self._repository = repository

    async def record(self, trace: RetrievalTrace) -> None:
        """Persist one completed trace atomically."""
        await self._repository.add(trace)
