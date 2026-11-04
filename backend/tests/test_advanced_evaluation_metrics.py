"""SP-24 measured ranking metrics and explicitly limited uncertainty reporting."""

from dataclasses import replace
from uuid import uuid4

import pytest

from spurel.evaluation_datasets.execution import (
    DatasetEvaluationCaseResult,
    DatasetEvaluationMode,
    _aggregate,
)
from spurel.evaluation_datasets.quality_reporting import wilson_hit_rate_95
from spurel.evaluation_datasets.run_domain import EvaluationRun
from spurel.evaluation_datasets.run_persistence import (
    EvaluationRunCaseRecord,
    EvaluationRunRecord,
)
from spurel.retrieval.evaluation import RelevanceJudgment, calculate_retrieval_metrics


def _metrics(*, hit: bool) -> object:
    ids = [uuid4() for _ in range(4)]
    judgments = (
        RelevanceJudgment(chunk_id=ids[0], relevance=3),
        RelevanceJudgment(chunk_id=ids[1], relevance=0),
        RelevanceJudgment(chunk_id=ids[2], relevance=1),
        RelevanceJudgment(chunk_id=ids[3], relevance=2),
    )
    ranked = (ids[1], ids[2], ids[0]) if hit else (ids[1],)
    return calculate_retrieval_metrics(
        cutoff=3, ranked_chunk_ids=ranked, judgments=judgments
    )


def _aggregate_two_cases():
    cases = (
        DatasetEvaluationCaseResult(
            case_id=uuid4(), query="first", duration_ms=12.0,
            metrics=_metrics(hit=True),
        ),
        DatasetEvaluationCaseResult(
            case_id=uuid4(), query="second", duration_ms=18.0,
            metrics=_metrics(hit=False),
        ),
    )
    return _aggregate(
        dataset_id=uuid4(),
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=3,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        cases=cases,
    )


def test_hit_and_average_precision_use_rank_order_and_graded_relevance_threshold() -> None:
    hit = _metrics(hit=True)
    assert hit.hit_at_k is True
    # Positive grades at ranks 2 and 3: AP=(1/2+2/3)/min(3,3).
    assert hit.average_precision_at_k == pytest.approx((0.5 + 2 / 3) / 3)
    assert hit.reciprocal_rank_at_k == 0.5
    assert hit.relevant_retrieved_at_k == 2

    miss = _metrics(hit=False)
    assert miss.hit_at_k is False
    assert miss.average_precision_at_k == 0.0
    assert miss.reciprocal_rank_at_k == 0.0


def test_macros_and_wilson_score_interval_are_measured_from_labeled_cases() -> None:
    result = _aggregate_two_cases()
    assert result.case_count == 2
    assert result.hit_rate_at_k == 0.5
    assert result.mean_average_precision_at_k == pytest.approx(
        ((0.5 + 2 / 3) / 3) / 2
    )
    interval = wilson_hit_rate_95(successes=1, trials=2)
    assert result.hit_rate_wilson_95_lower == pytest.approx(interval[0])
    assert result.hit_rate_wilson_95_upper == pytest.approx(interval[1])
    assert 0 <= interval[0] <= 0.5 <= interval[1] <= 1


@pytest.mark.parametrize("wins,total", [(0, 1), (1, 1), (0, 50), (50, 50)])
def test_wilson_remains_bounded_for_extreme_or_tiny_samples(wins: int, total: int) -> None:
    lower, upper = wilson_hit_rate_95(successes=wins, trials=total)
    assert 0 <= lower <= wins / total <= upper <= 1
    assert upper - lower > 0


@pytest.mark.parametrize("wins,total", [(-1, 2), (3, 2), (0, 0), (True, 4), (1, False)])
def test_wilson_rejects_impossible_or_untyped_counts(wins: int, total: int) -> None:
    with pytest.raises(ValueError):
        wilson_hit_rate_95(successes=wins, trials=total)


def test_extended_metrics_survive_run_and_case_snapshots() -> None:
    execution = _aggregate_two_cases()
    run = EvaluationRun.from_execution(knowledge_base_id=uuid4(), result=execution)
    saved = EvaluationRunRecord.from_domain(run)
    assert saved.hit_rate_at_k == 0.5
    assert saved.mean_average_precision_at_k == execution.mean_average_precision_at_k
    assert saved.hit_rate_wilson_95_lower == execution.hit_rate_wilson_95_lower
    assert saved.to_summary().hit_rate_at_k == 0.5
    assert saved.to_domain(cases=run.cases).mean_average_precision_at_k == (
        execution.mean_average_precision_at_k
    )
    first = EvaluationRunCaseRecord.from_domain(run_id=run.id, case=run.cases[0])
    assert first.hit_at_k is True
    assert first.to_domain(cutoff=3).metrics.average_precision_at_k == (
        execution.cases[0].metrics.average_precision_at_k
    )


def test_legacy_run_values_remain_null_instead_of_recalculated_or_fabricated() -> None:
    result = _aggregate_two_cases()
    legacy_cases = tuple(
        replace(
            case,
            metrics=replace(case.metrics, hit_at_k=None, average_precision_at_k=None),
        )
        for case in result.cases
    )
    old = _aggregate(
        dataset_id=result.dataset_id,
        mode=result.mode,
        top_k=result.top_k,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        cases=legacy_cases,
    )
    assert old.hit_rate_at_k is None
    assert old.mean_average_precision_at_k is None
    assert old.hit_rate_wilson_95_lower is None
    assert old.hit_rate_wilson_95_upper is None
