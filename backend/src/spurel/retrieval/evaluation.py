"""Deterministic evaluation metrics for historical retrieval traces."""

from dataclasses import dataclass
from math import log2
from typing import Protocol
from uuid import UUID

from spurel.retrieval.tracing import RetrievalTrace

MAX_RELEVANCE_GRADE = 3
MAX_EVALUATION_JUDGMENTS = 10_000


class RetrievalEvaluationQueryError(ValueError):
    """Raised when retrieval evaluation input is invalid."""


class RetrievalTraceReader(Protocol):
    """Scoped historical trace capability required by evaluation."""

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace:
        """Return one knowledge-base-scoped historical trace."""
        ...


@dataclass(frozen=True, slots=True)
class RelevanceJudgment:
    """Explicit graded relevance label for one historical chunk identity."""

    chunk_id: UUID
    relevance: int


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    """Deterministic retrieval metrics at one cutoff."""

    trace_id: UUID
    cutoff: int
    judged_count: int
    relevant_count: int
    retrieved_count_at_k: int
    judged_retrieved_at_k: int
    relevant_retrieved_at_k: int
    judgment_coverage_at_k: float | None
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank_at_k: float
    ndcg_at_k: float


class RetrievalEvaluationService:
    """Evaluate a historical retrieval trace against explicit judgments."""

    def __init__(self, trace_service: RetrievalTraceReader) -> None:
        self._trace_service = trace_service

    async def evaluate(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
        cutoff: int,
        judgments: tuple[RelevanceJudgment, ...],
    ) -> RetrievalEvaluation:
        """Load a scoped trace and compute deterministic retrieval metrics."""
        trace = await self._trace_service.get_by_id(
            knowledge_base_id=knowledge_base_id,
            trace_id=trace_id,
        )
        return evaluate_trace(
            trace=trace,
            cutoff=cutoff,
            judgments=judgments,
        )


def evaluate_trace(
    *,
    trace: RetrievalTrace,
    cutoff: int,
    judgments: tuple[RelevanceJudgment, ...],
) -> RetrievalEvaluation:
    """Compute Precision@K, Recall@K, MRR@K, and nDCG@K."""
    _validate_inputs(trace=trace, cutoff=cutoff, judgments=judgments)

    relevance_by_chunk = {
        judgment.chunk_id: judgment.relevance for judgment in judgments
    }
    relevant_count = sum(
        1 for relevance in relevance_by_chunk.values() if relevance > 0
    )

    top_results = trace.results[:cutoff]
    retrieved_count = len(top_results)
    retrieved_relevances = tuple(
        relevance_by_chunk.get(result.chunk_id, 0) for result in top_results
    )

    judged_retrieved = sum(
        1 for result in top_results if result.chunk_id in relevance_by_chunk
    )
    relevant_retrieved = sum(
        1 for relevance in retrieved_relevances if relevance > 0
    )

    first_relevant_rank = next(
        (
            rank
            for rank, relevance in enumerate(retrieved_relevances, start=1)
            if relevance > 0
        ),
        None,
    )

    dcg = _dcg(retrieved_relevances)
    ideal_relevances = tuple(
        sorted(relevance_by_chunk.values(), reverse=True)[:cutoff]
    )
    ideal_dcg = _dcg(ideal_relevances)

    return RetrievalEvaluation(
        trace_id=trace.id,
        cutoff=cutoff,
        judged_count=len(judgments),
        relevant_count=relevant_count,
        retrieved_count_at_k=retrieved_count,
        judged_retrieved_at_k=judged_retrieved,
        relevant_retrieved_at_k=relevant_retrieved,
        judgment_coverage_at_k=(
            judged_retrieved / retrieved_count if retrieved_count else None
        ),
        precision_at_k=relevant_retrieved / cutoff,
        recall_at_k=relevant_retrieved / relevant_count,
        reciprocal_rank_at_k=(
            1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0
        ),
        ndcg_at_k=dcg / ideal_dcg,
    )


def _validate_inputs(
    *,
    trace: RetrievalTrace,
    cutoff: int,
    judgments: tuple[RelevanceJudgment, ...],
) -> None:
    if (
        isinstance(cutoff, bool)
        or not isinstance(cutoff, int)
        or cutoff < 1
        or cutoff > trace.top_k
    ):
        raise RetrievalEvaluationQueryError(
            "evaluation cutoff must be between 1 and the trace top_k"
        )

    if not judgments or len(judgments) > MAX_EVALUATION_JUDGMENTS:
        raise RetrievalEvaluationQueryError(
            "evaluation judgments are outside the supported range"
        )

    seen_chunk_ids: set[UUID] = set()
    relevant_count = 0

    for judgment in judgments:
        if judgment.chunk_id in seen_chunk_ids:
            raise RetrievalEvaluationQueryError(
                "evaluation judgments contain duplicate chunk IDs"
            )
        seen_chunk_ids.add(judgment.chunk_id)

        if (
            isinstance(judgment.relevance, bool)
            or not isinstance(judgment.relevance, int)
            or judgment.relevance < 0
            or judgment.relevance > MAX_RELEVANCE_GRADE
        ):
            raise RetrievalEvaluationQueryError(
                "evaluation relevance grade is invalid"
            )

        if judgment.relevance > 0:
            relevant_count += 1

    if relevant_count == 0:
        raise RetrievalEvaluationQueryError(
            "evaluation requires at least one relevant judgment"
        )


def _dcg(relevances: tuple[int, ...]) -> float:
    return sum(
        ((2**relevance) - 1) / log2(rank + 1)
        for rank, relevance in enumerate(relevances, start=1)
    )
