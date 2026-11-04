"""Application decorators that persist successful retrieval executions."""

from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol
from uuid import UUID

from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.metadata_filters import RetrievalMetadataFilters
from spurel.retrieval.reranking import (
    CrossEncoderReranker,
    HttpCrossEncoderReranker,
    rerank_hybrid_matches,
)
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.timings import capture_stage_timings, time_stage
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


class VectorRetrievalRunner(Protocol):
    """Vector retrieval capability consumed by the tracing decorator."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
        filters: RetrievalMetadataFilters | None = None,
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
        filters: RetrievalMetadataFilters | None = None,
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
        filters: RetrievalMetadataFilters | None = None,
    ) -> Sequence[HybridRetrievalMatch]:
        """Return ranked hybrid matches."""
        ...


@dataclass(frozen=True, slots=True)
class TracedRetrievalResult[T]:
    """Successful retrieval output plus its durable trace identity."""

    trace_id: UUID
    duration_ms: float
    matches: tuple[T, ...]
    reranker_model: str | None = None
    stage_timings_ms: dict[str, float] | None = None


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
        filters: RetrievalMetadataFilters | None = None,
    ) -> TracedRetrievalResult[VectorRetrievalMatch]:
        """Run vector retrieval, persist its trace, then return both."""
        started = perf_counter()
        with capture_stage_timings() as stages:
            matches = tuple(
                await self._retriever.search(
                    knowledge_base_id=knowledge_base_id,
                    query=query,
                    limit=limit,
                    **({"filters": filters} if filters is not None else {}),
                )
            )
            duration_ms = _elapsed_ms(started)
        stage_timings = dict(stages) or None

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
            metadata_filters=filters,
            stage_timings_ms=stage_timings,
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
            stage_timings_ms=stage_timings,
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
        filters: RetrievalMetadataFilters | None = None,
    ) -> TracedRetrievalResult[KeywordRetrievalMatch]:
        """Run keyword retrieval, persist its trace, then return both."""
        started = perf_counter()
        with capture_stage_timings() as stages:
            matches = tuple(
                await self._retriever.search(
                    knowledge_base_id=knowledge_base_id,
                    query=query,
                    limit=limit,
                    **({"filters": filters} if filters is not None else {}),
                )
            )
            duration_ms = _elapsed_ms(started)
        stage_timings = dict(stages) or None

        trace = RetrievalTrace.create(
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.KEYWORD,
            query=query,
            top_k=limit,
            duration_ms=duration_ms,
            results=_keyword_trace_results(matches),
            metadata_filters=filters,
            stage_timings_ms=stage_timings,
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
            stage_timings_ms=stage_timings,
        )


class TracedHybridRetrievalService:
    """Record exact RRF searches or explicitly reranked candidate pools."""

    def __init__(
        self,
        *,
        retriever: HybridRetrievalRunner,
        trace_service: RetrievalTraceService,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimensions: int,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self._retriever = retriever
        self._trace_service = trace_service
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._reranker = reranker

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
        candidate_limit: int = 50,
        rrf_k: int = 60,
        filters: RetrievalMetadataFilters | None = None,
        rerank: bool = False,
    ) -> TracedRetrievalResult[HybridRetrievalMatch]:
        """Keep ordinary RRF exact; optional reranking is explicit and traced."""
        # Fail before expensive vector retrieval when no scoring adapter exists.
        reranker = (self._reranker or HttpCrossEncoderReranker.from_env()) if rerank else None
        started = perf_counter()
        with capture_stage_timings() as stages:
            matches = tuple(
                await self._retriever.search(
                    knowledge_base_id=knowledge_base_id,
                    query=query,
                    limit=candidate_limit if rerank else limit,
                    candidate_limit=candidate_limit,
                    rrf_k=rrf_k,
                    **({"filters": filters} if filters is not None else {}),
                )
            )
            if reranker is not None and matches:
                with time_stage("cross_encoder"):
                    matches = await rerank_hybrid_matches(
                        reranker=reranker,
                        query=query.strip(),
                        candidates=matches,
                        top_k=limit,
                    )
            duration_ms = _elapsed_ms(started)
        stage_timings = dict(stages) or None

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
            metadata_filters=filters,
            stage_timings_ms=stage_timings,
            reranker_model=reranker.model if reranker is not None else None,
        )
        await self._trace_service.record(trace)

        return TracedRetrievalResult(
            trace_id=trace.id,
            duration_ms=duration_ms,
            matches=matches,
            reranker_model=reranker.model if reranker is not None else None,
            stage_timings_ms=stage_timings,
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
            candidate_rank=match.candidate_rank,
            rerank_rank=match.rerank_rank,
            rerank_score=match.rerank_score,
        )
        for rank, match in enumerate(matches, start=1)
    )
