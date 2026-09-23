"""Retrieval trace domain values for reproducible experiments."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from uuid import UUID, uuid4

from spurel.embeddings.chunk import (
    MAX_EMBEDDING_MODEL_LENGTH,
    MAX_EMBEDDING_PROVIDER_LENGTH,
)
from spurel.embeddings.domain import MAX_EMBEDDING_DIMENSIONS


class RetrievalTraceMode(StrEnum):
    """Supported retrieval trace modes."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class RetrievalTraceValidationError(ValueError):
    """Raised when a retrieval trace is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class RetrievalTraceResult:
    """Immutable snapshot of one ranked retrieval result."""

    rank: int
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    cosine_similarity: float | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    vector_rank: int | None = None
    keyword_rank: int | None = None


@dataclass(frozen=True, slots=True)
class RetrievalTraceSummary:
    """Lightweight retrieval trace metadata for history views."""

    id: UUID
    knowledge_base_id: UUID
    mode: RetrievalTraceMode
    query: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    duration_ms: float
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    result_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    """One completed retrieval run and its reproducible configuration."""

    id: UUID
    knowledge_base_id: UUID
    mode: RetrievalTraceMode
    query: str
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    duration_ms: float
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    results: tuple[RetrievalTraceResult, ...]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        knowledge_base_id: UUID,
        mode: RetrievalTraceMode,
        query: str,
        top_k: int,
        duration_ms: float,
        results: tuple[RetrievalTraceResult, ...],
        candidate_k: int | None = None,
        rrf_k: int | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
    ) -> "RetrievalTrace":
        """Create and validate one completed retrieval trace."""
        normalized_query = query.strip()
        if not normalized_query or len(normalized_query) > 8_000:
            raise RetrievalTraceValidationError("trace query is invalid")

        if isinstance(top_k, bool) or top_k < 1 or top_k > 100:
            raise RetrievalTraceValidationError("trace top_k is invalid")

        if not isfinite(float(duration_ms)) or duration_ms < 0:
            raise RetrievalTraceValidationError("trace duration is invalid")

        if len(results) > top_k:
            raise RetrievalTraceValidationError(
                "trace results exceed configured top_k"
            )

        seen_chunk_ids: set[UUID] = set()
        for expected_rank, result in enumerate(results, start=1):
            if result.rank != expected_rank:
                raise RetrievalTraceValidationError(
                    "trace result ranks must be contiguous and start at one"
                )
            if result.chunk_id in seen_chunk_ids:
                raise RetrievalTraceValidationError(
                    "trace results cannot contain duplicate chunks"
                )
            seen_chunk_ids.add(result.chunk_id)

            if result.chunk_index < 0:
                raise RetrievalTraceValidationError(
                    "trace result chunk index is invalid"
                )
            if result.start_offset < 0 or result.end_offset <= result.start_offset:
                raise RetrievalTraceValidationError(
                    "trace result source offsets are invalid"
                )
            if not result.text:
                raise RetrievalTraceValidationError(
                    "trace result text must not be empty"
                )

            if mode is RetrievalTraceMode.VECTOR:
                if result.cosine_similarity is None:
                    raise RetrievalTraceValidationError(
                        "vector trace results require cosine similarity"
                    )
                if any(
                    value is not None
                    for value in (
                        result.keyword_score,
                        result.rrf_score,
                        result.vector_rank,
                        result.keyword_rank,
                    )
                ):
                    raise RetrievalTraceValidationError(
                        "vector trace results contain incompatible scores"
                    )

            if mode is RetrievalTraceMode.KEYWORD:
                if result.keyword_score is None:
                    raise RetrievalTraceValidationError(
                        "keyword trace results require keyword score"
                    )
                if any(
                    value is not None
                    for value in (
                        result.cosine_similarity,
                        result.rrf_score,
                        result.vector_rank,
                        result.keyword_rank,
                    )
                ):
                    raise RetrievalTraceValidationError(
                        "keyword trace results contain incompatible scores"
                    )

            for score in (
                result.cosine_similarity,
                result.keyword_score,
                result.rrf_score,
            ):
                if score is not None and not isfinite(score):
                    raise RetrievalTraceValidationError(
                        "trace result scores must be finite"
                    )

            if mode is RetrievalTraceMode.HYBRID:
                if result.rrf_score is None:
                    raise RetrievalTraceValidationError(
                        "hybrid trace results require RRF score"
                    )
                if result.vector_rank is None and result.keyword_rank is None:
                    raise RetrievalTraceValidationError(
                        "hybrid trace results require at least one source rank"
                    )
                if result.vector_rank is not None:
                    if result.vector_rank < 1 or result.cosine_similarity is None:
                        raise RetrievalTraceValidationError(
                            "hybrid vector rank requires a vector score"
                        )
                elif result.cosine_similarity is not None:
                    raise RetrievalTraceValidationError(
                        "hybrid vector score requires a vector rank"
                    )

                if result.keyword_rank is not None:
                    if result.keyword_rank < 1 or result.keyword_score is None:
                        raise RetrievalTraceValidationError(
                            "hybrid keyword rank requires a keyword score"
                        )
                elif result.keyword_score is not None:
                    raise RetrievalTraceValidationError(
                        "hybrid keyword score requires a keyword rank"
                    )

        if mode is RetrievalTraceMode.HYBRID:
            if candidate_k is None or rrf_k is None:
                raise RetrievalTraceValidationError(
                    "hybrid traces require candidate_k and rrf_k"
                )
            if candidate_k < top_k or candidate_k > 100:
                raise RetrievalTraceValidationError(
                    "hybrid trace candidate_k is invalid"
                )
            if rrf_k < 1 or rrf_k > 1_000:
                raise RetrievalTraceValidationError(
                    "hybrid trace rrf_k is invalid"
                )
        elif candidate_k is not None or rrf_k is not None:
            raise RetrievalTraceValidationError(
                "non-hybrid traces cannot contain hybrid configuration"
            )

        has_embedding_space = any(
            value is not None
            for value in (
                embedding_provider,
                embedding_model,
                embedding_dimensions,
            )
        )
        complete_embedding_space = all(
            value is not None
            for value in (
                embedding_provider,
                embedding_model,
                embedding_dimensions,
            )
        )
        if has_embedding_space != complete_embedding_space:
            raise RetrievalTraceValidationError(
                "embedding space metadata must be complete"
            )

        if complete_embedding_space:
            assert embedding_provider is not None
            assert embedding_model is not None
            assert embedding_dimensions is not None

            if (
                not embedding_provider.strip()
                or len(embedding_provider.strip()) > MAX_EMBEDDING_PROVIDER_LENGTH
            ):
                raise RetrievalTraceValidationError(
                    "trace embedding provider is invalid"
                )
            if (
                not embedding_model.strip()
                or len(embedding_model.strip()) > MAX_EMBEDDING_MODEL_LENGTH
            ):
                raise RetrievalTraceValidationError(
                    "trace embedding model is invalid"
                )
            if (
                isinstance(embedding_dimensions, bool)
                or not isinstance(embedding_dimensions, int)
                or embedding_dimensions < 1
                or embedding_dimensions > MAX_EMBEDDING_DIMENSIONS
            ):
                raise RetrievalTraceValidationError(
                    "trace embedding dimensions are invalid"
                )

        if mode in {RetrievalTraceMode.VECTOR, RetrievalTraceMode.HYBRID}:
            if not complete_embedding_space:
                raise RetrievalTraceValidationError(
                    "vector-based traces require embedding space metadata"
                )
        elif complete_embedding_space:
            raise RetrievalTraceValidationError(
                "keyword traces cannot contain embedding space metadata"
            )

        return cls(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            mode=mode,
            query=normalized_query,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
            duration_ms=float(duration_ms),
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            results=results,
            created_at=datetime.now(UTC),
        )
