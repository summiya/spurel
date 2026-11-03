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
from spurel.evaluation_datasets.judgment_integrity import EvaluationJudgmentAudit


class EvaluationDatasetPersistenceError(RuntimeError):
    """Raised when evaluation dataset persistence cannot complete."""


class EvaluationDatasetLoadLimitError(RuntimeError):
    """Raised when a synchronous dataset evaluation would load too much data."""


class EvaluationJudgmentInvalidError(ValueError):
    """Raised when a new judgment points outside the current active index."""


class EvaluationJudgmentStaleError(RuntimeError):
    """Raised when an existing label no longer references an active chunk."""


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

    async def load_cases_for_evaluation(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        max_cases: int,
        max_total_judgments: int,
    ) -> Sequence[EvaluationCase] | None:
        """Load a bounded complete case set for synchronous evaluation."""
        ...

    async def audit_judgments(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        max_cases: int,
        max_total_judgments: int,
    ) -> EvaluationJudgmentAudit | None:
        """Report invalid historical labels, or None for an unscoped dataset."""
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
