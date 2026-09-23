"""Application-facing persistence port for retrieval traces."""

from typing import Protocol

from spurel.retrieval.tracing import RetrievalTrace


class RetrievalTracePersistenceError(RuntimeError):
    """Raised when retrieval trace persistence cannot complete."""


class RetrievalTraceRepository(Protocol):
    """Persist completed retrieval traces atomically."""

    async def add(self, trace: RetrievalTrace) -> None:
        """Persist a retrieval trace and all ranked result snapshots."""
        ...
