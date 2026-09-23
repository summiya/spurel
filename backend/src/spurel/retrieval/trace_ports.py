"""Application-facing persistence port for retrieval traces."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.retrieval.tracing import RetrievalTrace, RetrievalTraceSummary


class RetrievalTracePersistenceError(RuntimeError):
    """Raised when retrieval trace persistence cannot complete."""


class RetrievalTraceRepository(Protocol):
    """Persist and read completed retrieval traces."""

    async def add(self, trace: RetrievalTrace) -> None:
        """Persist a retrieval trace and all ranked result snapshots."""
        ...

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[RetrievalTraceSummary]:
        """Return a bounded trace-history page without loading result snapshots."""
        ...

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace | None:
        """Return one scoped trace with all ranked result snapshots."""
        ...
