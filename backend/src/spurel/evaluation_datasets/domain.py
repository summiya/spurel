"""Evaluation dataset domain models."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from spurel.retrieval.evaluation import (
    MAX_EVALUATION_JUDGMENTS,
    MAX_RELEVANCE_GRADE,
    RelevanceJudgment,
)

MAX_EVALUATION_DATASET_NAME_LENGTH = 120
MAX_EVALUATION_QUERY_LENGTH = 8_000


class EvaluationDatasetValidationError(ValueError):
    """Raised when evaluation dataset input is invalid."""


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    """Reusable collection of labeled retrieval queries."""

    id: UUID
    knowledge_base_id: UUID
    name: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        knowledge_base_id: UUID,
        name: str,
    ) -> "EvaluationDataset":
        """Create a normalized evaluation dataset."""
        normalized_name = name.strip()
        if (
            not normalized_name
            or len(normalized_name) > MAX_EVALUATION_DATASET_NAME_LENGTH
        ):
            raise EvaluationDatasetValidationError(
                "evaluation dataset name is invalid"
            )

        return cls(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            name=normalized_name,
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One reusable query plus explicit graded relevance judgments."""

    id: UUID
    dataset_id: UUID
    query: str
    judgments: tuple[RelevanceJudgment, ...]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        dataset_id: UUID,
        query: str,
        judgments: tuple[RelevanceJudgment, ...],
    ) -> "EvaluationCase":
        """Create and validate one labeled evaluation query."""
        normalized_query = query.strip()
        if not normalized_query or len(normalized_query) > MAX_EVALUATION_QUERY_LENGTH:
            raise EvaluationDatasetValidationError(
                "evaluation case query is invalid"
            )

        if not judgments or len(judgments) > MAX_EVALUATION_JUDGMENTS:
            raise EvaluationDatasetValidationError(
                "evaluation case judgments are outside the supported range"
            )

        seen_chunk_ids: set[UUID] = set()
        relevant_count = 0

        for judgment in judgments:
            if judgment.chunk_id in seen_chunk_ids:
                raise EvaluationDatasetValidationError(
                    "evaluation case judgments contain duplicate chunk IDs"
                )
            seen_chunk_ids.add(judgment.chunk_id)

            if (
                isinstance(judgment.relevance, bool)
                or not isinstance(judgment.relevance, int)
                or judgment.relevance < 0
                or judgment.relevance > MAX_RELEVANCE_GRADE
            ):
                raise EvaluationDatasetValidationError(
                    "evaluation case relevance grade is invalid"
                )

            if judgment.relevance > 0:
                relevant_count += 1

        if relevant_count == 0:
            raise EvaluationDatasetValidationError(
                "evaluation case requires at least one relevant judgment"
            )

        return cls(
            id=uuid4(),
            dataset_id=dataset_id,
            query=normalized_query,
            judgments=judgments,
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class EvaluationDatasetSummary:
    """Lightweight dataset metadata for list views."""

    dataset: EvaluationDataset
    case_count: int


@dataclass(frozen=True, slots=True)
class EvaluationCaseSummary:
    """Lightweight case metadata without loading all judgments."""

    id: UUID
    dataset_id: UUID
    query: str
    judgment_count: int
    relevant_judgment_count: int
    created_at: datetime
