"""Application-facing persistence port for evaluation datasets."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
)


class EvaluationDatasetPersistenceError(RuntimeError):
    """Raised when evaluation dataset persistence cannot complete."""


class EvaluationDatasetRepository(Protocol):
    """Persist and read reusable evaluation datasets."""

    async def add_dataset(self, dataset: EvaluationDataset) -> None:
        """Persist one evaluation dataset."""
        ...

    async def list_datasets(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationDatasetSummary]:
        """Return a bounded dataset page."""
        ...

    async def add_case(
        self,
        *,
        knowledge_base_id: UUID,
        case: EvaluationCase,
    ) -> bool:
        """Persist one case atomically; return false when dataset is not scoped."""
        ...

    async def list_cases(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationCaseSummary] | None:
        """Return case summaries, or none when the scoped dataset is absent."""
        ...

    async def get_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase | None:
        """Return one scoped case with all persisted judgments."""
        ...
