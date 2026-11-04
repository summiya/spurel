"""Application-layer hybrid retrieval with reciprocal rank fusion."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch

MAX_HYBRID_RETRIEVAL_RESULTS = 100
DEFAULT_HYBRID_CANDIDATE_LIMIT = 50
DEFAULT_RRF_K = 60
MAX_RRF_K = 1_000


class HybridRetrievalQueryError(ValueError):
    """Raised when hybrid retrieval parameters are invalid."""


class HybridRetrievalResultError(RuntimeError):
    """Raised when retrievers disagree about persisted chunk identity."""


class VectorRetriever(Protocol):
    """Vector retrieval capability consumed by hybrid fusion."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        """Return ranked vector matches."""
        ...


class KeywordRetriever(Protocol):
    """Keyword retrieval capability consumed by hybrid fusion."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Return ranked keyword matches."""
        ...


@dataclass(frozen=True, slots=True)
class HybridRetrievalMatch:
    """One fused chunk with source ranks and scores preserved."""

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


@dataclass(slots=True)
class _HybridCandidate:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    rrf_score: float = 0.0
    vector_rank: int | None = None
    keyword_rank: int | None = None
    cosine_similarity: float | None = None
    keyword_score: float | None = None


class HybridRetrievalService:
    """Fuse vector and keyword retrieval using reciprocal rank fusion."""

    def __init__(
        self,
        *,
        vector_retriever: VectorRetriever,
        keyword_retriever: KeywordRetriever,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._keyword_retriever = keyword_retriever

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
        candidate_limit: int = DEFAULT_HYBRID_CANDIDATE_LIMIT,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> Sequence[HybridRetrievalMatch]:
        """Retrieve both sources concurrently and fuse their rankings."""
        normalized_query = query.strip()
        _validate_hybrid_query(
            query=normalized_query,
            limit=limit,
            candidate_limit=candidate_limit,
            rrf_k=rrf_k,
        )

        vector_matches, keyword_matches = await asyncio.gather(
            self._vector_retriever.search(
                knowledge_base_id=knowledge_base_id,
                query=normalized_query,
                limit=candidate_limit,
            ),
            self._keyword_retriever.search(
                knowledge_base_id=knowledge_base_id,
                query=normalized_query,
                limit=candidate_limit,
            ),
        )

        candidates: dict[UUID, _HybridCandidate] = {}

        for rank, match in enumerate(vector_matches, start=1):
            candidate = _get_or_create_candidate(
                candidates=candidates,
                match=match,
            )
            candidate.vector_rank = rank
            candidate.cosine_similarity = match.cosine_similarity
            candidate.rrf_score += 1.0 / (rrf_k + rank)

        for rank, match in enumerate(keyword_matches, start=1):
            candidate = _get_or_create_candidate(
                candidates=candidates,
                match=match,
            )
            candidate.keyword_rank = rank
            candidate.keyword_score = match.keyword_score
            candidate.rrf_score += 1.0 / (rrf_k + rank)

        ranked = sorted(
            candidates.values(),
            key=lambda candidate: (
                -candidate.rrf_score,
                candidate.chunk_id,
            ),
        )

        return tuple(
            HybridRetrievalMatch(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                chunk_index=candidate.chunk_index,
                text=candidate.text,
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                rrf_score=candidate.rrf_score,
                vector_rank=candidate.vector_rank,
                keyword_rank=candidate.keyword_rank,
                cosine_similarity=candidate.cosine_similarity,
                keyword_score=candidate.keyword_score,
            )
            for candidate in ranked[:limit]
        )


def _validate_hybrid_query(
    *,
    query: str,
    limit: int,
    candidate_limit: int,
    rrf_k: int,
) -> None:
    if not query:
        raise HybridRetrievalQueryError(
            "hybrid retrieval query must not be empty"
        )

    for name, value in (
        ("result limit", limit),
        ("candidate limit", candidate_limit),
        ("RRF k", rrf_k),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise HybridRetrievalQueryError(f"{name} must be an integer")

    if limit < 1 or limit > MAX_HYBRID_RETRIEVAL_RESULTS:
        raise HybridRetrievalQueryError(
            "hybrid result limit is outside the supported range"
        )

    if (
        candidate_limit < limit
        or candidate_limit > MAX_HYBRID_RETRIEVAL_RESULTS
    ):
        raise HybridRetrievalQueryError(
            "hybrid candidate limit must be at least the result limit and at most 100"
        )

    if rrf_k < 1 or rrf_k > MAX_RRF_K:
        raise HybridRetrievalQueryError(
            "RRF k is outside the supported range"
        )


def _get_or_create_candidate(
    *,
    candidates: dict[UUID, _HybridCandidate],
    match: VectorRetrievalMatch | KeywordRetrievalMatch,
) -> _HybridCandidate:
    existing = candidates.get(match.chunk_id)
    if existing is None:
        candidate = _HybridCandidate(
            chunk_id=match.chunk_id,
            document_id=match.document_id,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
        )
        candidates[match.chunk_id] = candidate
        return candidate

    if (
        existing.document_id != match.document_id
        or existing.chunk_index != match.chunk_index
        or existing.text != match.text
        or existing.start_offset != match.start_offset
        or existing.end_offset != match.end_offset
    ):
        raise HybridRetrievalResultError(
            "retrievers returned inconsistent metadata for the same chunk"
        )

    return existing
