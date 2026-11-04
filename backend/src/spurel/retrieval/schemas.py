"""HTTP schemas for Retrieval Playground endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from spurel.documents.domain import DocumentMediaType
from spurel.retrieval.evaluation import (
    MAX_EVALUATION_JUDGMENTS,
    MAX_RELEVANCE_GRADE,
)
from spurel.retrieval.metadata_filters import RetrievalMetadataFilters
from spurel.retrieval.tracing import RetrievalTraceMode


class RetrievalMetadataFiltersRequest(BaseModel):
    """Validated filters for fields already present on source documents."""

    model_config = ConfigDict(extra="forbid")

    document_ids: list[UUID] = Field(default_factory=list, max_length=20)
    media_types: list[DocumentMediaType] = Field(default_factory=list, max_length=3)
    filename_contains: str | None = Field(default=None, min_length=1, max_length=100)
    created_after: datetime | None = None
    created_before: datetime | None = None

    @model_validator(mode="after")
    def validate_metadata(self) -> "RetrievalMetadataFiltersRequest":
        self.to_domain()
        return self

    def to_domain(self) -> RetrievalMetadataFilters:
        return RetrievalMetadataFilters(
            document_ids=tuple(self.document_ids),
            media_types=tuple(self.media_types),
            filename_contains=self.filename_contains,
            created_after=self.created_after,
            created_before=self.created_before,
        )


class VectorRetrievalRequest(BaseModel):
    """Request payload for exact vector retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: RetrievalMetadataFiltersRequest | None = None


class VectorRetrievalMatchResponse(BaseModel):
    """Public ranked retrieval match."""

    rank: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    cosine_similarity: float
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    ocr_used: bool = False


class VectorRetrievalResponse(BaseModel):
    """Public Retrieval Playground response."""

    mode: Literal["vector"] = "vector"
    trace_id: UUID
    duration_ms: float = Field(ge=0)
    query: str
    top_k: int
    matches: list[VectorRetrievalMatchResponse]
    filters: RetrievalMetadataFiltersRequest | None = None


class KeywordRetrievalRequest(BaseModel):
    """Request payload for lexical keyword retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: RetrievalMetadataFiltersRequest | None = None


class KeywordRetrievalMatchResponse(BaseModel):
    """Public ranked keyword retrieval match."""

    rank: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    keyword_score: float
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    ocr_used: bool = False


class KeywordRetrievalResponse(BaseModel):
    """Public keyword Retrieval Playground response."""

    mode: Literal["keyword"] = "keyword"
    trace_id: UUID
    duration_ms: float = Field(ge=0)
    query: str
    top_k: int
    matches: list[KeywordRetrievalMatchResponse]
    filters: RetrievalMetadataFiltersRequest | None = None


class HybridRetrievalRequest(BaseModel):
    """Request payload for vector + keyword RRF retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: RetrievalMetadataFiltersRequest | None = None
    candidate_k: int = Field(default=50, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=1_000)
    rerank: StrictBool = False

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> "HybridRetrievalRequest":
        """Require enough source candidates to satisfy the final top-k."""
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")
        return self


class HybridRetrievalMatchResponse(BaseModel):
    """Public fused retrieval match with source traces."""

    rank: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    rrf_score: float
    vector_rank: int | None
    keyword_rank: int | None
    cosine_similarity: float | None
    keyword_score: float | None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    ocr_used: bool = False
    candidate_rank: int | None = Field(default=None, ge=1)
    rerank_rank: int | None = Field(default=None, ge=1)
    rerank_score: float | None = None


class HybridRetrievalResponse(BaseModel):
    """Public hybrid Retrieval Playground response."""

    mode: Literal["hybrid"] = "hybrid"
    trace_id: UUID
    duration_ms: float = Field(ge=0)
    query: str
    top_k: int
    candidate_k: int
    rrf_k: int
    matches: list[HybridRetrievalMatchResponse]
    filters: RetrievalMetadataFiltersRequest | None = None
    rerank: bool = False
    reranker_model: str | None = None


class RetrievalTraceSummaryResponse(BaseModel):
    """Public retrieval trace history summary."""

    id: UUID
    mode: RetrievalTraceMode
    query: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    duration_ms: float = Field(ge=0)
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    result_count: int = Field(ge=0, le=100)
    reranker_model: str | None = None
    filters: RetrievalMetadataFiltersRequest | None = None
    created_at: datetime


class RetrievalTraceListResponse(BaseModel):
    """Bounded retrieval trace history page."""

    items: list[RetrievalTraceSummaryResponse]
    limit: int
    offset: int


class RetrievalTraceResultResponse(BaseModel):
    """Historical ranked result snapshot."""

    rank: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    cosine_similarity: float | None
    keyword_score: float | None
    rrf_score: float | None
    vector_rank: int | None
    keyword_rank: int | None
    candidate_rank: int | None = None
    rerank_rank: int | None = None
    rerank_score: float | None = None


class RetrievalTraceDetailResponse(BaseModel):
    """Complete historical retrieval trace."""

    id: UUID
    knowledge_base_id: UUID
    mode: RetrievalTraceMode
    query: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    duration_ms: float = Field(ge=0)
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    created_at: datetime
    filters: RetrievalMetadataFiltersRequest | None = None
    reranker_model: str | None = None
    results: list[RetrievalTraceResultResponse]


class RetrievalTraceComparisonRequest(BaseModel):
    """Request payload for comparing two historical retrieval runs."""

    first_trace_id: UUID
    second_trace_id: UUID

    @model_validator(mode="after")
    def validate_distinct_traces(self) -> "RetrievalTraceComparisonRequest":
        """Require two distinct historical runs."""
        if self.first_trace_id == self.second_trace_id:
            raise ValueError("trace comparison requires two distinct trace IDs")
        return self


class RetrievalTraceComparisonSideResponse(BaseModel):
    """Configuration summary for one comparison side."""

    trace_id: UUID
    mode: RetrievalTraceMode
    query: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    duration_ms: float = Field(ge=0)
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    result_count: int = Field(ge=0, le=100)
    filters: RetrievalMetadataFiltersRequest | None = None
    reranker_model: str | None = None


class RetrievalTraceComparisonResultResponse(BaseModel):
    """One historical chunk aligned across two trace rankings."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    first_rank: int | None
    second_rank: int | None
    rank_delta: int | None
    first_cosine_similarity: float | None
    second_cosine_similarity: float | None
    first_keyword_score: float | None
    second_keyword_score: float | None
    first_rrf_score: float | None
    second_rrf_score: float | None
    first_candidate_rank: int | None = None
    second_candidate_rank: int | None = None
    first_rerank_score: float | None = None
    second_rerank_score: float | None = None


class RetrievalTraceComparisonResponse(BaseModel):
    """Descriptive side-by-side comparison of two retrieval traces."""

    first: RetrievalTraceComparisonSideResponse
    second: RetrievalTraceComparisonSideResponse
    same_query: bool
    overlap_count: int = Field(ge=0, le=100)
    union_count: int = Field(ge=0, le=200)
    overlap_ratio: float | None = Field(default=None, ge=0, le=1)
    first_only_count: int = Field(ge=0, le=100)
    second_only_count: int = Field(ge=0, le=100)
    duration_delta_ms: float
    results: list[RetrievalTraceComparisonResultResponse]


class RelevanceJudgmentRequest(BaseModel):
    """Explicit graded relevance judgment for one historical chunk."""

    chunk_id: UUID
    relevance: int = Field(ge=0, le=MAX_RELEVANCE_GRADE)


class RetrievalEvaluationRequest(BaseModel):
    """Request payload for deterministic trace evaluation."""

    cutoff: int = Field(ge=1, le=100)
    judgments: list[RelevanceJudgmentRequest] = Field(
        min_length=1,
        max_length=MAX_EVALUATION_JUDGMENTS,
    )


class RetrievalEvaluationResponse(BaseModel):
    """Deterministic retrieval metrics for one historical trace."""

    trace_id: UUID
    cutoff: int
    judged_count: int
    relevant_count: int
    retrieved_count_at_k: int
    judged_retrieved_at_k: int
    relevant_retrieved_at_k: int
    judgment_coverage_at_k: float | None = Field(default=None, ge=0, le=1)
    precision_at_k: float = Field(ge=0, le=1)
    recall_at_k: float = Field(ge=0, le=1)
    reciprocal_rank_at_k: float = Field(ge=0, le=1)
    ndcg_at_k: float = Field(ge=0, le=1)
