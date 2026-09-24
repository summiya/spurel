"""Side-by-side comparison of persisted evaluation benchmark runs."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunCase


class EvaluationRunReader(Protocol):
    """Scoped persisted run reader required by comparison."""

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        """Return one scoped persisted benchmark run."""
        ...


class EvaluationRunComparisonQueryError(ValueError):
    """Raised when an evaluation run comparison request is invalid."""


class EvaluationRunCasePresence(StrEnum):
    """Presence of one historical case across compared benchmark runs."""

    BOTH = "both"
    FIRST_ONLY = "first_only"
    SECOND_ONLY = "second_only"


@dataclass(frozen=True, slots=True)
class EvaluationRunComparisonSide:
    """Configuration and aggregate snapshot for one comparison side."""

    run_id: UUID
    mode: DatasetEvaluationMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    case_count: int
    total_duration_ms: float
    mean_duration_ms: float
    judgment_coverage_case_count: int
    mean_judgment_coverage_at_k: float | None
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr_at_k: float
    mean_ndcg_at_k: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationRunCaseComparison:
    """One historical evaluation case aligned across two runs."""

    case_id: UUID
    presence: EvaluationRunCasePresence
    first_position: int | None
    second_position: int | None
    first_query: str | None
    second_query: str | None
    query_changed: bool
    comparable: bool

    first_duration_ms: float | None
    second_duration_ms: float | None
    duration_delta_ms: float | None

    first_precision_at_k: float | None
    second_precision_at_k: float | None
    precision_delta: float | None

    first_recall_at_k: float | None
    second_recall_at_k: float | None
    recall_delta: float | None

    first_reciprocal_rank_at_k: float | None
    second_reciprocal_rank_at_k: float | None
    reciprocal_rank_delta: float | None

    first_ndcg_at_k: float | None
    second_ndcg_at_k: float | None
    ndcg_delta: float | None


@dataclass(frozen=True, slots=True)
class EvaluationRunComparison:
    """Descriptive metric deltas between two persisted benchmark runs."""

    dataset_id: UUID
    first: EvaluationRunComparisonSide
    second: EvaluationRunComparisonSide

    same_retrieval_configuration: bool
    same_case_set: bool
    aggregate_comparable: bool
    shared_case_count: int
    first_only_case_count: int
    second_only_case_count: int
    comparable_case_count: int
    query_changed_case_count: int

    total_duration_delta_ms: float | None
    mean_duration_delta_ms: float | None
    mean_judgment_coverage_delta: float | None
    mean_precision_delta: float | None
    mean_recall_delta: float | None
    mrr_delta: float | None
    mean_ndcg_delta: float | None

    cases: tuple[EvaluationRunCaseComparison, ...]


class EvaluationRunComparisonService:
    """Compare two scoped immutable benchmark runs."""

    def __init__(self, runs: EvaluationRunReader) -> None:
        self._runs = runs

    async def compare(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        first_run_id: UUID,
        second_run_id: UUID,
    ) -> EvaluationRunComparison:
        """Load both runs concurrently and compute descriptive deltas."""
        if first_run_id == second_run_id:
            raise EvaluationRunComparisonQueryError(
                "comparison requires two distinct evaluation run IDs"
            )

        first, second = await asyncio.gather(
            self._runs.get_by_id(
                knowledge_base_id=knowledge_base_id,
                dataset_id=dataset_id,
                run_id=first_run_id,
            ),
            self._runs.get_by_id(
                knowledge_base_id=knowledge_base_id,
                dataset_id=dataset_id,
                run_id=second_run_id,
            ),
        )

        return compare_evaluation_runs(first=first, second=second)


def compare_evaluation_runs(
    *,
    first: EvaluationRun,
    second: EvaluationRun,
) -> EvaluationRunComparison:
    """Compare two already-loaded runs from the same dataset identity."""
    if (
        first.knowledge_base_id != second.knowledge_base_id
        or first.dataset_id != second.dataset_id
    ):
        raise EvaluationRunComparisonQueryError(
            "evaluation runs must belong to the same scoped dataset"
        )

    first_cases = {case.case_id: case for case in first.cases}
    second_cases = {case.case_id: case for case in second.cases}
    first_ids = set(first_cases)
    second_ids = set(second_cases)
    shared_ids = first_ids & second_ids

    ordered_ids = sorted(
        first_ids | second_ids,
        key=lambda case_id: (
            first_cases[case_id].position if case_id in first_cases else 101,
            second_cases[case_id].position if case_id in second_cases else 101,
            str(case_id),
        ),
    )
    cases = tuple(
        _compare_case(
            first=first_cases.get(case_id),
            second=second_cases.get(case_id),
        )
        for case_id in ordered_ids
    )

    comparable_case_count = sum(1 for case in cases if case.comparable)
    query_changed_case_count = sum(1 for case in cases if case.query_changed)
    same_case_set = first_ids == second_ids
    aggregate_comparable = same_case_set and query_changed_case_count == 0

    return EvaluationRunComparison(
        dataset_id=first.dataset_id,
        first=_side(first),
        second=_side(second),
        same_retrieval_configuration=_same_configuration(first, second),
        same_case_set=same_case_set,
        aggregate_comparable=aggregate_comparable,
        shared_case_count=len(shared_ids),
        first_only_case_count=len(first_ids - second_ids),
        second_only_case_count=len(second_ids - first_ids),
        comparable_case_count=comparable_case_count,
        query_changed_case_count=query_changed_case_count,
        total_duration_delta_ms=(
            second.total_duration_ms - first.total_duration_ms
            if aggregate_comparable
            else None
        ),
        mean_duration_delta_ms=(
            second.mean_duration_ms - first.mean_duration_ms
            if aggregate_comparable
            else None
        ),
        mean_judgment_coverage_delta=(
            _optional_delta(
                first.mean_judgment_coverage_at_k,
                second.mean_judgment_coverage_at_k,
            )
            if aggregate_comparable
            else None
        ),
        mean_precision_delta=(
            second.mean_precision_at_k - first.mean_precision_at_k
            if aggregate_comparable
            else None
        ),
        mean_recall_delta=(
            second.mean_recall_at_k - first.mean_recall_at_k
            if aggregate_comparable
            else None
        ),
        mrr_delta=(
            second.mrr_at_k - first.mrr_at_k
            if aggregate_comparable
            else None
        ),
        mean_ndcg_delta=(
            second.mean_ndcg_at_k - first.mean_ndcg_at_k
            if aggregate_comparable
            else None
        ),
        cases=cases,
    )


def _compare_case(
    *,
    first: EvaluationRunCase | None,
    second: EvaluationRunCase | None,
) -> EvaluationRunCaseComparison:
    source = first or second
    assert source is not None

    if first is None:
        presence = EvaluationRunCasePresence.SECOND_ONLY
    elif second is None:
        presence = EvaluationRunCasePresence.FIRST_ONLY
    else:
        presence = EvaluationRunCasePresence.BOTH

    query_changed = (
        first is not None
        and second is not None
        and first.query != second.query
    )
    comparable = presence is EvaluationRunCasePresence.BOTH and not query_changed

    return EvaluationRunCaseComparison(
        case_id=source.case_id,
        presence=presence,
        first_position=first.position if first is not None else None,
        second_position=second.position if second is not None else None,
        first_query=first.query if first is not None else None,
        second_query=second.query if second is not None else None,
        query_changed=query_changed,
        comparable=comparable,
        first_duration_ms=first.duration_ms if first is not None else None,
        second_duration_ms=second.duration_ms if second is not None else None,
        duration_delta_ms=_case_delta(
            first_value=(first.duration_ms if first is not None else None),
            second_value=(second.duration_ms if second is not None else None),
            comparable=comparable,
        ),
        first_precision_at_k=(
            first.metrics.precision_at_k if first is not None else None
        ),
        second_precision_at_k=(
            second.metrics.precision_at_k if second is not None else None
        ),
        precision_delta=_case_delta(
            first_value=(
                first.metrics.precision_at_k if first is not None else None
            ),
            second_value=(
                second.metrics.precision_at_k if second is not None else None
            ),
            comparable=comparable,
        ),
        first_recall_at_k=(
            first.metrics.recall_at_k if first is not None else None
        ),
        second_recall_at_k=(
            second.metrics.recall_at_k if second is not None else None
        ),
        recall_delta=_case_delta(
            first_value=first.metrics.recall_at_k if first is not None else None,
            second_value=(
                second.metrics.recall_at_k if second is not None else None
            ),
            comparable=comparable,
        ),
        first_reciprocal_rank_at_k=(
            first.metrics.reciprocal_rank_at_k if first is not None else None
        ),
        second_reciprocal_rank_at_k=(
            second.metrics.reciprocal_rank_at_k if second is not None else None
        ),
        reciprocal_rank_delta=_case_delta(
            first_value=(
                first.metrics.reciprocal_rank_at_k
                if first is not None
                else None
            ),
            second_value=(
                second.metrics.reciprocal_rank_at_k
                if second is not None
                else None
            ),
            comparable=comparable,
        ),
        first_ndcg_at_k=first.metrics.ndcg_at_k if first is not None else None,
        second_ndcg_at_k=(
            second.metrics.ndcg_at_k if second is not None else None
        ),
        ndcg_delta=_case_delta(
            first_value=first.metrics.ndcg_at_k if first is not None else None,
            second_value=(
                second.metrics.ndcg_at_k if second is not None else None
            ),
            comparable=comparable,
        ),
    )


def _case_delta(
    *,
    first_value: float | None,
    second_value: float | None,
    comparable: bool,
) -> float | None:
    if not comparable or first_value is None or second_value is None:
        return None
    return second_value - first_value


def _optional_delta(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return second - first


def _side(run: EvaluationRun) -> EvaluationRunComparisonSide:
    return EvaluationRunComparisonSide(
        run_id=run.id,
        mode=run.mode,
        top_k=run.top_k,
        candidate_k=run.candidate_k,
        rrf_k=run.rrf_k,
        embedding_provider=run.embedding_provider,
        embedding_model=run.embedding_model,
        embedding_dimensions=run.embedding_dimensions,
        case_count=run.case_count,
        total_duration_ms=run.total_duration_ms,
        mean_duration_ms=run.mean_duration_ms,
        judgment_coverage_case_count=run.judgment_coverage_case_count,
        mean_judgment_coverage_at_k=run.mean_judgment_coverage_at_k,
        mean_precision_at_k=run.mean_precision_at_k,
        mean_recall_at_k=run.mean_recall_at_k,
        mrr_at_k=run.mrr_at_k,
        mean_ndcg_at_k=run.mean_ndcg_at_k,
        created_at=run.created_at,
    )


def _same_configuration(first: EvaluationRun, second: EvaluationRun) -> bool:
    return (
        first.mode == second.mode
        and first.top_k == second.top_k
        and first.candidate_k == second.candidate_k
        and first.rrf_k == second.rrf_k
        and first.embedding_provider == second.embedding_provider
        and first.embedding_model == second.embedding_model
        and first.embedding_dimensions == second.embedding_dimensions
    )
