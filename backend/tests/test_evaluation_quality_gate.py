from datetime import UTC, datetime
from uuid import uuid4

import pytest

from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.quality_gate import (
    EvaluationQualityGateMetric,
    EvaluationQualityGateRegressionKind,
    EvaluationQualityGateStatus,
    EvaluationQualityGateThresholdError,
    EvaluationQualityGateThresholds,
    evaluate_quality_gate,
)
from spurel.evaluation_datasets.run_comparison import (
    EvaluationRunComparison,
    EvaluationRunComparisonSide,
)


def _side(
    *,
    precision: float,
    recall: float,
    mrr: float,
    ndcg: float,
    coverage: float | None,
    duration_ms: float,
) -> EvaluationRunComparisonSide:
    return EvaluationRunComparisonSide(
        run_id=uuid4(),
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        case_count=3,
        total_duration_ms=duration_ms * 3,
        mean_duration_ms=duration_ms,
        judgment_coverage_case_count=3 if coverage is not None else 0,
        mean_judgment_coverage_at_k=coverage,
        mean_precision_at_k=precision,
        mean_recall_at_k=recall,
        mrr_at_k=mrr,
        mean_ndcg_at_k=ndcg,
        created_at=datetime.now(UTC),
    )


def _comparison(
    *,
    aggregate_comparable: bool = True,
    first_coverage: float | None = 0.8,
    second_coverage: float | None = 0.8,
) -> EvaluationRunComparison:
    first = _side(
        precision=0.70,
        recall=0.80,
        mrr=0.75,
        ndcg=0.78,
        coverage=first_coverage,
        duration_ms=100,
    )
    second = _side(
        precision=0.69,
        recall=0.77,
        mrr=0.73,
        ndcg=0.76,
        coverage=second_coverage,
        duration_ms=108,
    )
    return EvaluationRunComparison(
        dataset_id=uuid4(),
        first=first,
        second=second,
        same_retrieval_configuration=True,
        same_case_set=aggregate_comparable,
        aggregate_comparable=aggregate_comparable,
        shared_case_count=3 if aggregate_comparable else 2,
        first_only_case_count=0 if aggregate_comparable else 1,
        second_only_case_count=0,
        comparable_case_count=3 if aggregate_comparable else 2,
        query_changed_case_count=0,
        total_duration_delta_ms=24 if aggregate_comparable else None,
        mean_duration_delta_ms=8 if aggregate_comparable else None,
        mean_judgment_coverage_delta=(
            None
            if not aggregate_comparable
            or first_coverage is None
            or second_coverage is None
            else second_coverage - first_coverage
        ),
        mean_precision_delta=-0.01 if aggregate_comparable else None,
        mean_recall_delta=-0.03 if aggregate_comparable else None,
        mrr_delta=-0.02 if aggregate_comparable else None,
        mean_ndcg_delta=-0.02 if aggregate_comparable else None,
        cases=(),
    )


def test_quality_gate_passes_when_all_regressions_are_within_thresholds() -> None:
    result = evaluate_quality_gate(
        comparison=_comparison(),
        thresholds=EvaluationQualityGateThresholds(
            max_mean_precision_drop=0.02,
            max_mean_recall_drop=0.03,
            max_mrr_drop=0.02,
            max_mean_ndcg_drop=0.02,
            max_mean_duration_increase_ms=10,
        ),
    )

    assert result.status is EvaluationQualityGateStatus.PASS
    assert result.unavailable_metrics == ()
    assert len(result.checks) == 5
    assert all(check.passed for check in result.checks)

    duration = next(
        check
        for check in result.checks
        if check.metric is EvaluationQualityGateMetric.MEAN_DURATION_MS
    )
    assert duration.regression_kind is EvaluationQualityGateRegressionKind.INCREASE
    assert duration.delta == 8
    assert duration.regression_amount == 8


def test_quality_gate_fails_when_any_configured_threshold_is_exceeded() -> None:
    result = evaluate_quality_gate(
        comparison=_comparison(),
        thresholds=EvaluationQualityGateThresholds(
            max_mean_precision_drop=0.02,
            max_mean_recall_drop=0.01,
            max_mean_duration_increase_ms=5,
        ),
    )

    assert result.status is EvaluationQualityGateStatus.FAIL
    failed = {check.metric for check in result.checks if not check.passed}
    assert failed == {
        EvaluationQualityGateMetric.MEAN_RECALL_AT_K,
        EvaluationQualityGateMetric.MEAN_DURATION_MS,
    }


def test_quality_gate_exact_threshold_is_allowed() -> None:
    result = evaluate_quality_gate(
        comparison=_comparison(),
        thresholds=EvaluationQualityGateThresholds(
            max_mean_recall_drop=0.03,
            max_mean_duration_increase_ms=8,
        ),
    )

    assert result.status is EvaluationQualityGateStatus.PASS
    assert all(check.passed for check in result.checks)


def test_quality_gate_is_not_evaluable_when_case_structure_changed() -> None:
    thresholds = EvaluationQualityGateThresholds(
        max_mrr_drop=0.02,
        max_mean_ndcg_drop=0.02,
    )
    result = evaluate_quality_gate(
        comparison=_comparison(aggregate_comparable=False),
        thresholds=thresholds,
    )

    assert result.status is EvaluationQualityGateStatus.NOT_EVALUABLE
    assert result.aggregate_comparable is False
    assert result.checks == ()
    assert result.unavailable_metrics == (
        EvaluationQualityGateMetric.MRR_AT_K,
        EvaluationQualityGateMetric.MEAN_NDCG_AT_K,
    )


def test_quality_gate_is_not_evaluable_when_configured_coverage_is_undefined() -> None:
    result = evaluate_quality_gate(
        comparison=_comparison(first_coverage=None, second_coverage=None),
        thresholds=EvaluationQualityGateThresholds(
            max_mean_precision_drop=0.02,
            max_mean_judgment_coverage_drop=0.05,
        ),
    )

    assert result.status is EvaluationQualityGateStatus.NOT_EVALUABLE
    assert result.unavailable_metrics == (
        EvaluationQualityGateMetric.MEAN_JUDGMENT_COVERAGE_AT_K,
    )
    assert len(result.checks) == 1
    assert result.checks[0].metric is EvaluationQualityGateMetric.MEAN_PRECISION_AT_K


def test_quality_gate_requires_at_least_one_threshold() -> None:
    with pytest.raises(EvaluationQualityGateThresholdError):
        evaluate_quality_gate(
            comparison=_comparison(),
            thresholds=EvaluationQualityGateThresholds(),
        )
