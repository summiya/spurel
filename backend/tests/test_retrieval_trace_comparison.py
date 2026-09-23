import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.trace_comparison import (
    RetrievalTraceComparisonIntegrityError,
    RetrievalTraceComparisonQueryError,
    RetrievalTraceComparisonService,
)
from spurel.retrieval.trace_service import RetrievalTraceNotFoundError
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


class FakeTraceService:
    def __init__(self, traces: tuple[RetrievalTrace, ...]) -> None:
        self._traces = {trace.id: trace for trace in traces}

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace:
        trace = self._traces.get(trace_id)
        if trace is None or trace.knowledge_base_id != knowledge_base_id:
            raise RetrievalTraceNotFoundError("missing")
        return trace


def _trace(
    *,
    knowledge_base_id: UUID,
    mode: RetrievalTraceMode,
    query: str,
    duration_ms: float,
    results: tuple[RetrievalTraceResult, ...],
) -> RetrievalTrace:
    is_keyword = mode is RetrievalTraceMode.KEYWORD
    return RetrievalTrace(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        mode=mode,
        query=query,
        top_k=10,
        candidate_k=50 if mode is RetrievalTraceMode.HYBRID else None,
        rrf_k=60 if mode is RetrievalTraceMode.HYBRID else None,
        duration_ms=duration_ms,
        embedding_provider=None if is_keyword else "openai",
        embedding_model=None if is_keyword else "model",
        embedding_dimensions=None if is_keyword else 1536,
        results=results,
        created_at=datetime.now(UTC),
    )


def _vector_result(
    *,
    chunk_id: UUID,
    document_id: UUID,
    rank: int,
    score: float,
    text: str | None = None,
) -> RetrievalTraceResult:
    return RetrievalTraceResult(
        rank=rank,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=rank - 1,
        text=text or f"chunk-{rank}",
        start_offset=(rank - 1) * 10,
        end_offset=((rank - 1) * 10) + 7,
        cosine_similarity=score,
    )


def _keyword_result(
    *,
    chunk_id: UUID,
    document_id: UUID,
    rank: int,
    score: float,
    chunk_index: int,
    text: str,
    start_offset: int,
    end_offset: int,
) -> RetrievalTraceResult:
    return RetrievalTraceResult(
        rank=rank,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        text=text,
        start_offset=start_offset,
        end_offset=end_offset,
        keyword_score=score,
    )


def test_comparison_reports_overlap_unique_chunks_and_rank_movement() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    shared = uuid4()
    first_only = uuid4()
    second_only = uuid4()

    first_shared = _vector_result(
        chunk_id=shared,
        document_id=document_id,
        rank=2,
        score=0.88,
        text="shared",
    )
    first = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.VECTOR,
        query="authentication",
        duration_ms=12.0,
        results=(
            _vector_result(
                chunk_id=first_only,
                document_id=document_id,
                rank=1,
                score=0.95,
            ),
            first_shared,
        ),
    )
    second = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.KEYWORD,
        query="authentication",
        duration_ms=8.0,
        results=(
            _keyword_result(
                chunk_id=shared,
                document_id=document_id,
                rank=1,
                score=0.8,
                chunk_index=first_shared.chunk_index,
                text=first_shared.text,
                start_offset=first_shared.start_offset,
                end_offset=first_shared.end_offset,
            ),
            _keyword_result(
                chunk_id=second_only,
                document_id=document_id,
                rank=2,
                score=0.7,
                chunk_index=9,
                text="second only",
                start_offset=90,
                end_offset=101,
            ),
        ),
    )

    service = RetrievalTraceComparisonService(FakeTraceService((first, second)))
    comparison = asyncio.run(
        service.compare(
            knowledge_base_id=knowledge_base_id,
            first_trace_id=first.id,
            second_trace_id=second.id,
        )
    )

    assert comparison.same_query is True
    assert comparison.overlap_count == 1
    assert comparison.union_count == 3
    assert comparison.overlap_ratio == pytest.approx(1 / 3)
    assert comparison.first_only_count == 1
    assert comparison.second_only_count == 1
    assert comparison.duration_delta_ms == -4.0

    shared_result = next(
        result for result in comparison.results if result.chunk_id == shared
    )
    assert shared_result.first_rank == 2
    assert shared_result.second_rank == 1
    assert shared_result.rank_delta == -1
    assert shared_result.first_cosine_similarity == 0.88
    assert shared_result.second_keyword_score == 0.8


def test_comparison_allows_different_queries_and_marks_them() -> None:
    knowledge_base_id = uuid4()
    first = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.KEYWORD,
        query="first query",
        duration_ms=1.0,
        results=(),
    )
    second = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.KEYWORD,
        query="second query",
        duration_ms=2.0,
        results=(),
    )
    service = RetrievalTraceComparisonService(FakeTraceService((first, second)))

    comparison = asyncio.run(
        service.compare(
            knowledge_base_id=knowledge_base_id,
            first_trace_id=first.id,
            second_trace_id=second.id,
        )
    )

    assert comparison.same_query is False
    assert comparison.overlap_count == 0
    assert comparison.union_count == 0
    assert comparison.overlap_ratio is None


def test_comparison_rejects_same_trace_id() -> None:
    trace_id = uuid4()
    service = RetrievalTraceComparisonService(FakeTraceService(()))

    with pytest.raises(RetrievalTraceComparisonQueryError):
        asyncio.run(
            service.compare(
                knowledge_base_id=uuid4(),
                first_trace_id=trace_id,
                second_trace_id=trace_id,
            )
        )


def test_comparison_rejects_conflicting_snapshot_metadata() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    first = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.VECTOR,
        query="query",
        duration_ms=1.0,
        results=(
            _vector_result(
                chunk_id=chunk_id,
                document_id=document_id,
                rank=1,
                score=0.9,
                text="original",
            ),
        ),
    )
    second_result = RetrievalTraceResult(
        rank=1,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        text="different snapshot text",
        start_offset=0,
        end_offset=7,
        cosine_similarity=0.8,
    )
    second = _trace(
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.VECTOR,
        query="query",
        duration_ms=2.0,
        results=(second_result,),
    )

    service = RetrievalTraceComparisonService(FakeTraceService((first, second)))

    with pytest.raises(RetrievalTraceComparisonIntegrityError):
        asyncio.run(
            service.compare(
                knowledge_base_id=knowledge_base_id,
                first_trace_id=first.id,
                second_trace_id=second.id,
            )
        )
