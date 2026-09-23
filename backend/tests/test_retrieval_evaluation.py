import asyncio
from datetime import UTC, datetime
from math import log2
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.evaluation import (
    RelevanceJudgment,
    RetrievalEvaluationQueryError,
    RetrievalEvaluationService,
    evaluate_trace,
)
from spurel.retrieval.trace_service import RetrievalTraceNotFoundError
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


def _result(*, rank: int, chunk_id: UUID) -> RetrievalTraceResult:
    return RetrievalTraceResult(
        rank=rank,
        chunk_id=chunk_id,
        document_id=uuid4(),
        chunk_index=rank - 1,
        text=f"chunk-{rank}",
        start_offset=(rank - 1) * 10,
        end_offset=((rank - 1) * 10) + 7,
        cosine_similarity=0.95 - (rank * 0.05),
    )


def _trace(
    *,
    knowledge_base_id: UUID,
    top_k: int,
    results: tuple[RetrievalTraceResult, ...],
) -> RetrievalTrace:
    return RetrievalTrace(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.VECTOR,
        query="authentication",
        top_k=top_k,
        candidate_k=None,
        rrf_k=None,
        duration_ms=12.5,
        embedding_provider="openai",
        embedding_model="model",
        embedding_dimensions=1536,
        results=results,
        created_at=datetime.now(UTC),
    )


def test_evaluation_computes_precision_recall_mrr_ndcg_and_coverage() -> None:
    knowledge_base_id = uuid4()
    first = uuid4()
    highly_relevant = uuid4()
    unjudged = uuid4()
    relevant = uuid4()
    missing_relevant = uuid4()

    trace = _trace(
        knowledge_base_id=knowledge_base_id,
        top_k=4,
        results=(
            _result(rank=1, chunk_id=first),
            _result(rank=2, chunk_id=highly_relevant),
            _result(rank=3, chunk_id=unjudged),
            _result(rank=4, chunk_id=relevant),
        ),
    )
    judgments = (
        RelevanceJudgment(chunk_id=first, relevance=0),
        RelevanceJudgment(chunk_id=highly_relevant, relevance=3),
        RelevanceJudgment(chunk_id=relevant, relevance=1),
        RelevanceJudgment(chunk_id=missing_relevant, relevance=2),
    )

    evaluation = evaluate_trace(
        trace=trace,
        cutoff=4,
        judgments=judgments,
    )

    expected_dcg = (7 / log2(3)) + (1 / log2(5))
    expected_idcg = 7 + (3 / log2(3)) + (1 / log2(4))

    assert evaluation.judged_count == 4
    assert evaluation.relevant_count == 3
    assert evaluation.retrieved_count_at_k == 4
    assert evaluation.judged_retrieved_at_k == 3
    assert evaluation.relevant_retrieved_at_k == 2
    assert evaluation.judgment_coverage_at_k == pytest.approx(3 / 4)
    assert evaluation.precision_at_k == pytest.approx(2 / 4)
    assert evaluation.recall_at_k == pytest.approx(2 / 3)
    assert evaluation.reciprocal_rank_at_k == pytest.approx(1 / 2)
    assert evaluation.ndcg_at_k == pytest.approx(expected_dcg / expected_idcg)


def test_evaluation_treats_unjudged_retrieved_chunks_as_non_relevant() -> None:
    judged_relevant = uuid4()
    unjudged = uuid4()
    trace = _trace(
        knowledge_base_id=uuid4(),
        top_k=2,
        results=(
            _result(rank=1, chunk_id=unjudged),
            _result(rank=2, chunk_id=judged_relevant),
        ),
    )

    evaluation = evaluate_trace(
        trace=trace,
        cutoff=2,
        judgments=(
            RelevanceJudgment(chunk_id=judged_relevant, relevance=1),
        ),
    )

    assert evaluation.precision_at_k == pytest.approx(0.5)
    assert evaluation.judgment_coverage_at_k == pytest.approx(0.5)
    assert evaluation.reciprocal_rank_at_k == pytest.approx(0.5)


def test_evaluation_returns_null_coverage_when_trace_retrieved_nothing() -> None:
    trace = _trace(
        knowledge_base_id=uuid4(),
        top_k=10,
        results=(),
    )

    evaluation = evaluate_trace(
        trace=trace,
        cutoff=5,
        judgments=(RelevanceJudgment(chunk_id=uuid4(), relevance=2),),
    )

    assert evaluation.retrieved_count_at_k == 0
    assert evaluation.judgment_coverage_at_k is None
    assert evaluation.precision_at_k == 0
    assert evaluation.recall_at_k == 0
    assert evaluation.reciprocal_rank_at_k == 0
    assert evaluation.ndcg_at_k == 0


@pytest.mark.parametrize(
    "judgments",
    [
        (),
        (
            RelevanceJudgment(chunk_id=UUID(int=1), relevance=0),
        ),
        (
            RelevanceJudgment(chunk_id=UUID(int=1), relevance=1),
            RelevanceJudgment(chunk_id=UUID(int=1), relevance=2),
        ),
    ],
)
def test_evaluation_rejects_incomplete_or_duplicate_judgments(
    judgments: tuple[RelevanceJudgment, ...],
) -> None:
    trace = _trace(
        knowledge_base_id=uuid4(),
        top_k=10,
        results=(),
    )

    with pytest.raises(RetrievalEvaluationQueryError):
        evaluate_trace(trace=trace, cutoff=5, judgments=judgments)


def test_evaluation_rejects_cutoff_beyond_trace_capture_depth() -> None:
    trace = _trace(
        knowledge_base_id=uuid4(),
        top_k=5,
        results=(),
    )

    with pytest.raises(RetrievalEvaluationQueryError):
        evaluate_trace(
            trace=trace,
            cutoff=6,
            judgments=(RelevanceJudgment(chunk_id=uuid4(), relevance=1),),
        )


class FakeTraceService:
    def __init__(self, trace: RetrievalTrace | None) -> None:
        self.trace = trace
        self.last_call: tuple[UUID, UUID] | None = None

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace:
        self.last_call = (knowledge_base_id, trace_id)
        if (
            self.trace is None
            or self.trace.knowledge_base_id != knowledge_base_id
            or self.trace.id != trace_id
        ):
            raise RetrievalTraceNotFoundError("missing")
        return self.trace


def test_evaluation_service_uses_scoped_trace_reader() -> None:
    knowledge_base_id = uuid4()
    relevant = uuid4()
    trace = _trace(
        knowledge_base_id=knowledge_base_id,
        top_k=5,
        results=(_result(rank=1, chunk_id=relevant),),
    )
    trace_service = FakeTraceService(trace)
    service = RetrievalEvaluationService(trace_service)  # type: ignore[arg-type]

    evaluation = asyncio.run(
        service.evaluate(
            knowledge_base_id=knowledge_base_id,
            trace_id=trace.id,
            cutoff=1,
            judgments=(RelevanceJudgment(chunk_id=relevant, relevance=1),),
        )
    )

    assert evaluation.trace_id == trace.id
    assert trace_service.last_call == (knowledge_base_id, trace.id)
