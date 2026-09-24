"""Persistence boundaries for explicit evaluation baselines."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselinePromotion,
)


class EvaluationBaselinePersistenceError(RuntimeError):
    """Raised when baseline persistence cannot complete."""


class EvaluationBaselineRepository(Protocol):
    """Persist and resolve explicitly promoted evaluation baselines."""

    async def upsert(self, baseline: EvaluationBaseline) -> EvaluationBaseline:
        """Promote the run and append its audit snapshot atomically."""
        ...

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaseline]:
        """Return a bounded newest-first baseline page."""
        ...

    async def list_history_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaselinePromotion]:
        """Return a bounded newest-first promotion audit page."""
        ...

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline | None:
        """Resolve the promoted baseline for one exact configuration."""
        ...
