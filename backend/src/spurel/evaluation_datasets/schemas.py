"""HTTP schemas for reusable evaluation datasets."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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


class DatasetEvaluationRequest(BaseModel):
    """Request payload for vector or keyword dataset evaluation."""

    top_k: int = Field(default=10, ge=1, le=100)


class HybridDatasetEvaluationRequest(BaseModel):
    """Request payload for hybrid dataset evaluation."""

    top_k: int = Field(default=10, ge=1, le=100)
    candidate_k: int = Field(default=50, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> "HybridDatasetEvaluationRequest":
        """Require enough source candidates for the requested final top-k."""
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")
        return self


class DatasetEvaluationCaseResponse(BaseModel):
    """Per-query metrics within one dataset evaluation run."""

    case_id: UUID
    query: str
    duration_ms: float = Field(ge=0)
    judged_count: int = Field(ge=1)
    relevant_count: int = Field(ge=1)
    retrieved_count_at_k: int = Field(ge=0, le=100)
    judged_retrieved_at_k: int = Field(ge=0, le=100)
    relevant_retrieved_at_k: int = Field(ge=0, le=100)
    judgment_coverage_at_k: float | None = Field(default=None, ge=0, le=1)
    precision_at_k: float = Field(ge=0, le=1)
    recall_at_k: float = Field(ge=0, le=1)
    reciprocal_rank_at_k: float = Field(ge=0, le=1)
    ndcg_at_k: float = Field(ge=0, le=1)


class DatasetEvaluationResponse(BaseModel):
    """Aggregate metrics for one synchronous dataset evaluation run."""

    dataset_id: UUID
    mode: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    case_count: int = Field(ge=1, le=100)
    total_duration_ms: float = Field(ge=0)
    mean_duration_ms: float = Field(ge=0)
    mean_judgment_coverage_at_k: float | None = Field(default=None, ge=0, le=1)
    mean_precision_at_k: float = Field(ge=0, le=1)
    mean_recall_at_k: float = Field(ge=0, le=1)
    mrr_at_k: float = Field(ge=0, le=1)
    mean_ndcg_at_k: float = Field(ge=0, le=1)
    cases: list[DatasetEvaluationCaseResponse]
