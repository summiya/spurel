"""HTTP schemas for Retrieval Playground endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    query: str
    top_k: int
    matches: list[KeywordRetrievalMatchResponse]
