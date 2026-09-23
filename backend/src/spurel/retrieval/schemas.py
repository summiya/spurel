"""HTTP schemas for Retrieval Playground endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from spurel.retrieval.tracing import RetrievalTraceMode


class VectorRetrievalRequest(BaseModel):
    """Request payload for exact vector retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)


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


class VectorRetrievalResponse(BaseModel):
    """Public Retrieval Playground response."""

    mode: Literal["vector"] = "vector"
    trace_id: UUID
    duration_ms: float = Field(ge=0)
    query: str
    top_k: int
    matches: list[VectorRetrievalMatchResponse]


class KeywordRetrievalRequest(BaseModel):
    """Request payload for lexical keyword retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)


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


class KeywordRetrievalResponse(BaseModel):
    """Public keyword Retrieval Playground response."""

    mode: Literal["keyword"] = "keyword"
    trace_id: UUID
    duration_ms: float = Field(ge=0)
    query: str
    top_k: int
    matches: list[KeywordRetrievalMatchResponse]


class HybridRetrievalRequest(BaseModel):
    """Request payload for vector + keyword RRF retrieval."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=10, ge=1, le=100)
    candidate_k: int = Field(default=50, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=1_000)

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


class RetrievalTraceComparisonResponse(BaseModel):
    """Descriptive side-by-side comparison of two retrieval traces."""

    first: RetrievalTraceComparisonSideResponse
    second: RetrievalTraceComparisonSideResponse
    same_query: bool
    overlap_count: int = Field(ge=0, le=100)
    union_count: int = Field(ge=0, le=200)
    overlap_ratio: float = Field(ge=0, le=1)
    first_only_count: int = Field(ge=0, le=100)
    second_only_count: int = Field(ge=0, le=100)
    duration_delta_ms: float
    results: list[RetrievalTraceComparisonResultResponse]
