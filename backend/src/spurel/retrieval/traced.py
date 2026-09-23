"""Application decorators that persist successful retrieval executions."""

from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)

T = TypeVar("T")


class VectorRetrievalRunner(Protocol):
    """Vector retrieval capability consumed by the tracing decorator."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        """Return ranked vector matches."""
        ...


class KeywordRetrievalRunner(Protocol):
    """Keyword retrieval capability consumed by the tracing decorator."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Return ranked keyword matches."""
        ...


class HybridRetrievalRunner(Protocol):
    """Hybrid retrieval capability consumed by the tracing decorator."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
        candidate_limit: int,
        rrf_k: int,
    ) -> Sequence[HybridRetrievalMatch]:
        """Return ranked hybrid matches."""
        ...


@dataclass(frozen=True, slots=True)
class TracedRetrievalResult(Generic[T]):
    """Successful retrieval output plus its durable trace identity."""

    trace_id: UUID
    duration_ms: float
    matches: tuple[T, ...]


class TracedVectorRetrievalService:
    """Record successful vector searches without changing the core retriever."""

    def __init__(
        self,
        *,
        retriever: VectorRetrievalRunner,
        trace_service: RetrievalTraceService,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        self._retriever = retriever
        self._trace_service = trace_service
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
    ) -> TracedRetrievalResult[VectorRetrievalMatch]:
        """Run vector retrieval, persist its trace, then return both."""
        started = perf_counter()
        matches = tuple(
            await self._retriever.search(
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
            )
        )
        duration_ms = _elapsed_ms(started)

        trace = RetrievalTrace.create(
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.VECTOR,
            query=query,
            top_k=limit,
            duration_ms=duration_ms,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_dimensions=self._embedding_dimensions,
            results=_vector_trace_results(matches),
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
        )


class TracedKeywordRetrievalService:
    """Record successful keyword searches without changing the core retriever."""

    def __init__(
        self,
        *,
        retriever: KeywordRetrievalRunner,
        trace_service: RetrievalTraceService,
    ) -> None:
        self._retriever = retriever
        self._trace_service = trace_service

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
    ) -> TracedRetrievalResult[KeywordRetrievalMatch]:
        """Run keyword retrieval, persist its trace, then return both."""
        started = perf_counter()
        matches = tuple(
            await self._retriever.search(
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
            )
        )
        duration_ms = _elapsed_ms(started)

        trace = RetrievalTrace.create(
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.KEYWORD,
            query=query,
            top_k=limit,
            duration_ms=duration_ms,
            results=_keyword_trace_results(matches),
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
        )


class TracedHybridRetrievalService:
    """Record successful RRF searches without changing hybrid fusion."""

    def __init__(
        self,
        *,
        retriever: HybridRetrievalRunner,
        trace_service: RetrievalTraceService,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        self._retriever = retriever
        self._trace_service = trace_service
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
        candidate_limit: int = 50,
        rrf_k: int = 60,
    ) -> TracedRetrievalResult[HybridRetrievalMatch]:
        """Run hybrid retrieval, persist its trace, then return both."""
        started = perf_counter()
        matches = tuple(
            await self._retriever.search(
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
                candidate_limit=candidate_limit,
                rrf_k=rrf_k,
            )
        )
        duration_ms = _elapsed_ms(started)

        trace = RetrievalTrace.create(
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.HYBRID,
            query=query,
            top_k=limit,
            candidate_k=candidate_limit,
            rrf_k=rrf_k,
            duration_ms=duration_ms,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_dimensions=self._embedding_dimensions,
            results=_hybrid_trace_results(matches),
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
        )


def _elapsed_ms(started: float) -> float:
    return max(0.0, (perf_counter() - started) * 1_000.0)


def _vector_trace_results(
    matches: Sequence[VectorRetrievalMatch],
) -> tuple[RetrievalTraceResult, ...]:
    return tuple(
        RetrievalTraceResult(
            rank=rank,
            chunk_id=match.chunk_id,
            document_id=match.document_id,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
            cosine_similarity=match.cosine_similarity,
        )
        for rank, match in enumerate(matches, start=1)
    )


def _keyword_trace_results(
    matches: Sequence[KeywordRetrievalMatch],
) -> tuple[RetrievalTraceResult, ...]:
    return tuple(
        RetrievalTraceResult(
            rank=rank,
            chunk_id=match.chunk_id,
            document_id=match.document_id,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
            keyword_score=match.keyword_score,
        )
        for rank, match in enumerate(matches, start=1)
    )


def _hybrid_trace_results(
    matches: Sequence[HybridRetrievalMatch],
) -> tuple[RetrievalTraceResult, ...]:
    return tuple(
        RetrievalTraceResult(
            rank=rank,
            chunk_id=match.chunk_id,
            document_id=match.document_id,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
            cosine_similarity=match.cosine_similarity,
            keyword_score=match.keyword_score,
            rrf_score=match.rrf_score,
            vector_rank=match.vector_rank,
            keyword_rank=match.keyword_rank,
        )
        for rank, match in enumerate(matches, start=1)
    )
