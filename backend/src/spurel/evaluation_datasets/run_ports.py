"""Persistence boundaries for historical evaluation runs."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary


class EvaluationRunPersistenceError(RuntimeError):
    """Raised when evaluation run persistence cannot complete."""


class EvaluationRunRepository(Protocol):
    """Persist and read immutable evaluation benchmark runs."""

    async def add(self, run: EvaluationRun) -> None:
        """Persist one run and all per-case snapshots atomically."""
        ...

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationRunSummary]:
        """Return a bounded newest-first run history page."""
        ...

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun | None:
        """Return one scoped run with all per-case metric snapshots."""
        ...
