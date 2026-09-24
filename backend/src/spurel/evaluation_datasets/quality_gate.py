"""Explicit threshold-based quality gates for benchmark run comparisons."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.run_comparison import EvaluationRunComparison


class EvaluationRunComparator(Protocol):
    """Run-comparison capability required by quality gates."""

    async def compare(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        first_run_id: UUID,
        second_run_id: UUID,
    ) -> EvaluationRunComparison:
        """Return one scoped persisted benchmark comparison."""
        ...


class EvaluationQualityGateStatus(StrEnum):
    """Deterministic quality-gate result."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class EvaluationQualityGateMetric(StrEnum):
    """Supported aggregate metrics for threshold checks."""

    MEAN_PRECISION_AT_K = "mean_precision_at_k"
    MEAN_RECALL_AT_K = "mean_recall_at_k"
    MRR_AT_K = "mrr_at_k"
    MEAN_NDCG_AT_K = "mean_ndcg_at_k"
    MEAN_JUDGMENT_COVERAGE_AT_K = "mean_judgment_coverage_at_k"
    MEAN_DURATION_MS = "mean_duration_ms"


class EvaluationQualityGateRegressionKind(StrEnum):
    """How a metric can regress relative to its baseline."""

    DROP = "drop"
    INCREASE = "increase"


class EvaluationQualityGateThresholdError(ValueError):
    """Raised when a quality-gate threshold configuration is invalid."""


@dataclass(frozen=True, slots=True)
class EvaluationQualityGateThresholds:
    """Maximum tolerated benchmark regressions."""

    max_mean_precision_drop: float | None = None
    max_mean_recall_drop: float | None = None
    max_mrr_drop: float | None = None
    max_mean_ndcg_drop: float | None = None
    max_mean_judgment_coverage_drop: float | None = None
    max_mean_duration_increase_ms: float | None = None

    def validate(self) -> None:
        """Require at least one valid explicit threshold."""
        values = (
            self.max_mean_precision_drop,
            self.max_mean_recall_drop,
            self.max_mrr_drop,
            self.max_mean_ndcg_drop,
            self.max_mean_judgment_coverage_drop,
            self.max_mean_duration_increase_ms,
        )
        if all(value is None for value in values):
            raise EvaluationQualityGateThresholdError(
                "at least one quality-gate threshold is required"
            )

        for value in (
            self.max_mean_precision_drop,
            self.max_mean_recall_drop,
            self.max_mrr_drop,
            self.max_mean_ndcg_drop,
            self.max_mean_judgment_coverage_drop,
        ):
            if value is not None and (value < 0 or value > 1):
                raise EvaluationQualityGateThresholdError(
                    "metric-drop thresholds must be between zero and one"
                )

        if (
            self.max_mean_duration_increase_ms is not None
            and self.max_mean_duration_increase_ms < 0
        ):
            raise EvaluationQualityGateThresholdError(
                "duration threshold cannot be negative"
            )


@dataclass(frozen=True, slots=True)
class EvaluationQualityGateCheck:
    """Evidence for one configured threshold."""

    metric: EvaluationQualityGateMetric
    regression_kind: EvaluationQualityGateRegressionKind
    first_value: float
    second_value: float
    delta: float
    allowed_regression: float
    regression_amount: float
    passed: bool


@dataclass(frozen=True, slots=True)
class EvaluationQualityGateResult:
    """Deterministic threshold evaluation for two benchmark runs."""

    status: EvaluationQualityGateStatus
    aggregate_comparable: bool
    same_retrieval_configuration: bool
    unavailable_metrics: tuple[EvaluationQualityGateMetric, ...]
    checks: tuple[EvaluationQualityGateCheck, ...]


def evaluate_quality_gate(
    *,
    comparison: EvaluationRunComparison,
    thresholds: EvaluationQualityGateThresholds,
) -> EvaluationQualityGateResult:
    """Evaluate explicit thresholds against a run comparison."""
    thresholds.validate()

    if not comparison.aggregate_comparable:
        return EvaluationQualityGateResult(
            status=EvaluationQualityGateStatus.NOT_EVALUABLE,
            aggregate_comparable=False,
            same_retrieval_configuration=comparison.same_retrieval_configuration,
            unavailable_metrics=_configured_metrics(thresholds),
            checks=(),
        )

    checks: list[EvaluationQualityGateCheck] = []
    unavailable_metrics: list[EvaluationQualityGateMetric] = []

    _append_higher_is_better_check(
        checks=checks,
        metric=EvaluationQualityGateMetric.MEAN_PRECISION_AT_K,
        first_value=comparison.first.mean_precision_at_k,
        second_value=comparison.second.mean_precision_at_k,
        allowed_drop=thresholds.max_mean_precision_drop,
    )
    _append_higher_is_better_check(
        checks=checks,
        metric=EvaluationQualityGateMetric.MEAN_RECALL_AT_K,
        first_value=comparison.first.mean_recall_at_k,
        second_value=comparison.second.mean_recall_at_k,
        allowed_drop=thresholds.max_mean_recall_drop,
    )
    _append_higher_is_better_check(
        checks=checks,
        metric=EvaluationQualityGateMetric.MRR_AT_K,
        first_value=comparison.first.mrr_at_k,
        second_value=comparison.second.mrr_at_k,
        allowed_drop=thresholds.max_mrr_drop,
    )
    _append_higher_is_better_check(
        checks=checks,
        metric=EvaluationQualityGateMetric.MEAN_NDCG_AT_K,
        first_value=comparison.first.mean_ndcg_at_k,
        second_value=comparison.second.mean_ndcg_at_k,
        allowed_drop=thresholds.max_mean_ndcg_drop,
    )

    if thresholds.max_mean_judgment_coverage_drop is not None:
        first_coverage = comparison.first.mean_judgment_coverage_at_k
        second_coverage = comparison.second.mean_judgment_coverage_at_k
        if first_coverage is None or second_coverage is None:
            unavailable_metrics.append(
                EvaluationQualityGateMetric.MEAN_JUDGMENT_COVERAGE_AT_K
            )
        else:
            _append_higher_is_better_check(
                checks=checks,
                metric=EvaluationQualityGateMetric.MEAN_JUDGMENT_COVERAGE_AT_K,
                first_value=first_coverage,
                second_value=second_coverage,
                allowed_drop=thresholds.max_mean_judgment_coverage_drop,
            )

    if thresholds.max_mean_duration_increase_ms is not None:
        _append_lower_is_better_check(
            checks=checks,
            metric=EvaluationQualityGateMetric.MEAN_DURATION_MS,
            first_value=comparison.first.mean_duration_ms,
            second_value=comparison.second.mean_duration_ms,
            allowed_increase=thresholds.max_mean_duration_increase_ms,
        )

    if unavailable_metrics:
        status = EvaluationQualityGateStatus.NOT_EVALUABLE
    else:
        status = (
            EvaluationQualityGateStatus.PASS
            if all(check.passed for check in checks)
            else EvaluationQualityGateStatus.FAIL
        )

    return EvaluationQualityGateResult(
        status=status,
        aggregate_comparable=True,
        same_retrieval_configuration=comparison.same_retrieval_configuration,
        unavailable_metrics=tuple(unavailable_metrics),
        checks=tuple(checks),
    )


def _append_higher_is_better_check(
    *,
    checks: list[EvaluationQualityGateCheck],
    metric: EvaluationQualityGateMetric,
    first_value: float,
    second_value: float,
    allowed_drop: float | None,
) -> None:
    if allowed_drop is None:
        return

    delta = second_value - first_value
    regression_amount = max(0.0, -delta)
    checks.append(
        EvaluationQualityGateCheck(
            metric=metric,
            regression_kind=EvaluationQualityGateRegressionKind.DROP,
            first_value=first_value,
            second_value=second_value,
            delta=delta,
            allowed_regression=allowed_drop,
            regression_amount=regression_amount,
            passed=regression_amount <= allowed_drop,
        )
    )


def _append_lower_is_better_check(
    *,
    checks: list[EvaluationQualityGateCheck],
    metric: EvaluationQualityGateMetric,
    first_value: float,
    second_value: float,
    allowed_increase: float,
) -> None:
    delta = second_value - first_value
    regression_amount = max(0.0, delta)
    checks.append(
        EvaluationQualityGateCheck(
            metric=metric,
            regression_kind=EvaluationQualityGateRegressionKind.INCREASE,
            first_value=first_value,
            second_value=second_value,
            delta=delta,
            allowed_regression=allowed_increase,
            regression_amount=regression_amount,
            passed=regression_amount <= allowed_increase,
        )
    )


def _configured_metrics(
    thresholds: EvaluationQualityGateThresholds,
) -> tuple[EvaluationQualityGateMetric, ...]:
    configured: list[EvaluationQualityGateMetric] = []

    if thresholds.max_mean_precision_drop is not None:
        configured.append(EvaluationQualityGateMetric.MEAN_PRECISION_AT_K)
    if thresholds.max_mean_recall_drop is not None:
        configured.append(EvaluationQualityGateMetric.MEAN_RECALL_AT_K)
    if thresholds.max_mrr_drop is not None:
        configured.append(EvaluationQualityGateMetric.MRR_AT_K)
    if thresholds.max_mean_ndcg_drop is not None:
        configured.append(EvaluationQualityGateMetric.MEAN_NDCG_AT_K)
    if thresholds.max_mean_judgment_coverage_drop is not None:
        configured.append(
            EvaluationQualityGateMetric.MEAN_JUDGMENT_COVERAGE_AT_K
        )
    if thresholds.max_mean_duration_increase_ms is not None:
        configured.append(EvaluationQualityGateMetric.MEAN_DURATION_MS)

    return tuple(configured)



class EvaluationQualityGateService:
    """Apply explicit thresholds to a scoped persisted run comparison."""

    def __init__(self, comparisons: EvaluationRunComparator) -> None:
        self._comparisons = comparisons

    async def evaluate(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        first_run_id: UUID,
        second_run_id: UUID,
        thresholds: EvaluationQualityGateThresholds,
    ) -> EvaluationQualityGateResult:
        """Compare two runs and evaluate the configured quality gate."""
        thresholds.validate()
        comparison = await self._comparisons.compare(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            first_run_id=first_run_id,
            second_run_id=second_run_id,
        )
        return evaluate_quality_gate(
            comparison=comparison,
            thresholds=thresholds,
        )
