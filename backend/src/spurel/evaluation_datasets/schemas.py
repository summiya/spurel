"""HTTP schemas for reusable evaluation datasets."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from spurel.evaluation_datasets.domain import (
    MAX_EVALUATION_DATASET_NAME_LENGTH,
    MAX_EVALUATION_QUERY_LENGTH,
)
from spurel.retrieval.evaluation import (
    MAX_EVALUATION_JUDGMENTS,
    MAX_RELEVANCE_GRADE,
)


class CreateEvaluationDatasetRequest(BaseModel):
    """Payload for creating one reusable evaluation dataset."""

    name: str = Field(
        min_length=1,
        max_length=MAX_EVALUATION_DATASET_NAME_LENGTH,
    )


class EvaluationDatasetResponse(BaseModel):
    """Public evaluation dataset summary."""

    id: UUID
    knowledge_base_id: UUID
    name: str
    case_count: int = Field(ge=0)
    created_at: datetime


class EvaluationDatasetListResponse(BaseModel):
    """Bounded evaluation dataset page."""

    items: list[EvaluationDatasetResponse]
    limit: int
    offset: int


class EvaluationJudgmentRequest(BaseModel):
    """One graded relevance label for a dataset case."""

    chunk_id: UUID
    relevance: int = Field(ge=0, le=MAX_RELEVANCE_GRADE)


class CreateEvaluationCaseRequest(BaseModel):
    """Payload for creating one labeled evaluation query."""

    query: str = Field(min_length=1, max_length=MAX_EVALUATION_QUERY_LENGTH)
    judgments: list[EvaluationJudgmentRequest] = Field(
        min_length=1,
        max_length=MAX_EVALUATION_JUDGMENTS,
    )


class EvaluationJudgmentResponse(BaseModel):
    """Public persisted relevance judgment."""

    chunk_id: UUID
    relevance: int = Field(ge=0, le=MAX_RELEVANCE_GRADE)


class EvaluationCaseResponse(BaseModel):
    """Complete reusable evaluation case."""

    id: UUID
    dataset_id: UUID
    query: str
    judgments: list[EvaluationJudgmentResponse]
    created_at: datetime


class EvaluationCaseSummaryResponse(BaseModel):
    """Lightweight evaluation case metadata."""

    id: UUID
    dataset_id: UUID
    query: str
    judgment_count: int = Field(ge=0)
    relevant_judgment_count: int = Field(ge=0)
    created_at: datetime


class EvaluationCaseListResponse(BaseModel):
    """Bounded evaluation case summary page."""

    items: list[EvaluationCaseSummaryResponse]
    limit: int
    offset: int
