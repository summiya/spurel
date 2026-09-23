"""Side-by-side comparison of historical retrieval traces."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


class RetrievalTraceComparisonQueryError(ValueError):
    """Raised when a trace comparison request is invalid."""


class RetrievalTraceComparisonIntegrityError(RuntimeError):
    """Raised when historical trace snapshots conflict."""


@dataclass(frozen=True, slots=True)
class RetrievalTraceComparisonSide:
    """Configuration summary for one side of a trace comparison."""

    trace_id: UUID
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


@dataclass(frozen=True, slots=True)
class RetrievalTraceComparisonResult:
    """One chunk aligned across two historical ranked result sets."""

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


@dataclass(frozen=True, slots=True)
class RetrievalTraceComparison:
    """Descriptive comparison between two historical retrieval runs."""

    first: RetrievalTraceComparisonSide
    second: RetrievalTraceComparisonSide
    same_query: bool
    overlap_count: int
    union_count: int
    overlap_ratio: float
    first_only_count: int
    second_only_count: int
    duration_delta_ms: float
    results: tuple[RetrievalTraceComparisonResult, ...]


class RetrievalTraceComparisonService:
    """Compare two scoped historical traces without modifying them."""

    def __init__(self, trace_service: RetrievalTraceService) -> None:
        self._trace_service = trace_service

    async def compare(
        self,
        *,
        knowledge_base_id: UUID,
        first_trace_id: UUID,
        second_trace_id: UUID,
    ) -> RetrievalTraceComparison:
        """Load two traces and describe ranking/result differences."""
        if first_trace_id == second_trace_id:
            raise RetrievalTraceComparisonQueryError(
                "comparison requires two distinct trace IDs"
            )

        first, second = await asyncio.gather(
            self._trace_service.get_by_id(
                knowledge_base_id=knowledge_base_id,
                trace_id=first_trace_id,
            ),
            self._trace_service.get_by_id(
                knowledge_base_id=knowledge_base_id,
                trace_id=second_trace_id,
            ),
        )

        return _compare_traces(first=first, second=second)


def _compare_traces(
    *,
    first: RetrievalTrace,
    second: RetrievalTrace,
) -> RetrievalTraceComparison:
    first_by_chunk = {result.chunk_id: result for result in first.results}
    second_by_chunk = {result.chunk_id: result for result in second.results}

    first_ids = set(first_by_chunk)
    second_ids = set(second_by_chunk)
    shared_ids = first_ids & second_ids
    union_ids = first_ids | second_ids

    aligned = sorted(
        union_ids,
        key=lambda chunk_id: (
            first_by_chunk[chunk_id].rank
            if chunk_id in first_by_chunk
            else 101,
            second_by_chunk[chunk_id].rank
            if chunk_id in second_by_chunk
            else 101,
            chunk_id,
        ),
    )

    results = tuple(
        _compare_result(
            first_result=first_by_chunk.get(chunk_id),
            second_result=second_by_chunk.get(chunk_id),
        )
        for chunk_id in aligned
    )

    union_count = len(union_ids)
    overlap_count = len(shared_ids)

    return RetrievalTraceComparison(
        first=_side(first),
        second=_side(second),
        same_query=first.query == second.query,
        overlap_count=overlap_count,
        union_count=union_count,
        overlap_ratio=(overlap_count / union_count) if union_count else 1.0,
        first_only_count=len(first_ids - second_ids),
        second_only_count=len(second_ids - first_ids),
        duration_delta_ms=second.duration_ms - first.duration_ms,
        results=results,
    )


def _compare_result(
    *,
    first_result: RetrievalTraceResult | None,
    second_result: RetrievalTraceResult | None,
) -> RetrievalTraceComparisonResult:
    source = first_result or second_result
    assert source is not None

    if first_result is not None and second_result is not None:
        if (
            first_result.document_id != second_result.document_id
            or first_result.chunk_index != second_result.chunk_index
            or first_result.text != second_result.text
            or first_result.start_offset != second_result.start_offset
            or first_result.end_offset != second_result.end_offset
        ):
            raise RetrievalTraceComparisonIntegrityError(
                "trace snapshots disagree about metadata for the same chunk"
            )

    first_rank = first_result.rank if first_result is not None else None
    second_rank = second_result.rank if second_result is not None else None
    rank_delta = (
        second_rank - first_rank
        if first_rank is not None and second_rank is not None
        else None
    )

    return RetrievalTraceComparisonResult(
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        chunk_index=source.chunk_index,
        text=source.text,
        start_offset=source.start_offset,
        end_offset=source.end_offset,
        first_rank=first_rank,
        second_rank=second_rank,
        rank_delta=rank_delta,
        first_cosine_similarity=(
            first_result.cosine_similarity if first_result is not None else None
        ),
        second_cosine_similarity=(
            second_result.cosine_similarity if second_result is not None else None
        ),
        first_keyword_score=(
            first_result.keyword_score if first_result is not None else None
        ),
        second_keyword_score=(
            second_result.keyword_score if second_result is not None else None
        ),
        first_rrf_score=(
            first_result.rrf_score if first_result is not None else None
        ),
        second_rrf_score=(
            second_result.rrf_score if second_result is not None else None
        ),
    )


def _side(trace: RetrievalTrace) -> RetrievalTraceComparisonSide:
    return RetrievalTraceComparisonSide(
        trace_id=trace.id,
        mode=trace.mode,
        query=trace.query,
        top_k=trace.top_k,
        candidate_k=trace.candidate_k,
        rrf_k=trace.rrf_k,
        duration_ms=trace.duration_ms,
        embedding_provider=trace.embedding_provider,
        embedding_model=trace.embedding_model,
        embedding_dimensions=trace.embedding_dimensions,
        result_count=len(trace.results),
    )
