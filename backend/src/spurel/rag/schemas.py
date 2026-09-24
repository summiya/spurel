"""HTTP schemas for retrieval-augmented answer generation."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RAGAnswerRequest(BaseModel):
    """Request payload for one grounded answer."""

    query: str = Field(min_length=1, max_length=8_000)
    top_k: int = Field(default=8, ge=1, le=20)
    candidate_k: int = Field(default=50, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> "RAGAnswerRequest":
        """Require enough retrieval candidates for the requested context."""
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")
        return self


class RAGAnswerResponse(BaseModel):
    """Public grounded-answer response."""

    trace_id: UUID
    answer: str
    retrieved_chunk_count: int = Field(ge=0, le=20)
    generation_provider: str | None
    generation_model: str | None
