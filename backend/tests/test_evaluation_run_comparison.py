import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_comparison import (
    EvaluationRunCasePresence,
    EvaluationRunComparisonQueryError,
    EvaluationRunComparisonService,
    compare_evaluation_runs,
)
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunCase
from spurel.retrieval.evaluation import RetrievalMetricValues


def _metrics(
    *,
    precision: float,
    recall: float,
    rr: float,
    ndcg: float,
) -> RetrievalMetricValues:
    return RetrievalMetricValues(
        cutoff=10,
        judged_count=4,
        relevant_count=2,
        retrieved_count_at_k=10,
        judged_retrieved_at_k=4,
        relevant_retrieved_at_k=2,
        judgment_coverage_at_k=0.4,
        precision_at_k=precision,
        recall_at_k=recall,
        reciprocal_rank_at_k=rr,
        ndcg_at_k=ndcg,
    )


def _case(
    *,
    case_id: UUID,
    position: int,
    query: str,
    duration_ms: float,
    precision: float,
    recall: float,
    rr: float,
    ndcg: float,
) -> EvaluationRunCase:
    return EvaluationRunCase(
        position=position,
        case_id=case_id,
        query=query,
        duration_ms=duration_ms,
        metrics=_metrics(
            precision=precision,
            recall=recall,
            rr=rr,
            ndcg=ndcg,
        ),
    )


def _run(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    mode: DatasetEvaluationMode,
    cases: tuple[EvaluationRunCase, ...],
    mean_precision: float,
    mean_recall: float,
    mrr: float,
    mean_ndcg: float,
    total_duration_ms: float,
    embedding_model: str | None = None,
) -> EvaluationRun:
    uses_embeddings = mode is not DatasetEvaluationMode.KEYWORD
    return EvaluationRun(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=mode,
        top_k=10,
        candidate_k=50 if mode is DatasetEvaluationMode.HYBRID else None,
        rrf_k=60 if mode is DatasetEvaluationMode.HYBRID else None,
        embedding_provider="openai" if uses_embeddings else None,
        embedding_model=(
            embedding_model or "model-a"
            if uses_embeddings
            else None
        ),
        embedding_dimensions=1536 if uses_embeddings else None,
        case_count=len(cases),
        total_duration_ms=total_duration_ms,
        mean_duration_ms=total_duration_ms / len(cases),
        judgment_coverage_case_count=len(cases),
        mean_judgment_coverage_at_k=0.4,
        mean_precision_at_k=mean_precision,
        mean_recall_at_k=mean_recall,
        mrr_at_k=mrr,
        mean_ndcg_at_k=mean_ndcg,
        cases=cases,
        created_at=datetime.now(UTC),
    )


def test_run_comparison_reports_aggregate_and_per_case_deltas() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    first_case_id = uuid4()
    second_case_id = uuid4()

    first = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.VECTOR,
        cases=(
            _case(
                case_id=first_case_id,
                position=1,
                query="authentication",
                duration_ms=10.0,
                precision=0.2,
                recall=0.5,
                rr=0.5,
                ndcg=0.6,
            ),
            _case(
                case_id=second_case_id,
                position=2,
                query="authorization",
                duration_ms=20.0,
                precision=0.3,
                recall=0.6,
                rr=0.5,
                ndcg=0.7,
            ),
        ),
        mean_precision=0.25,
        mean_recall=0.55,
        mrr=0.5,
        mean_ndcg=0.65,
        total_duration_ms=30.0,
        embedding_model="model-a",
    )
    second = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.VECTOR,
        cases=(
            _case(
                case_id=first_case_id,
                position=1,
                query="authentication",
                duration_ms=8.0,
                precision=0.4,
                recall=0.7,
                rr=1.0,
                ndcg=0.8,
            ),
            _case(
                case_id=second_case_id,
                position=2,
                query="authorization",
                duration_ms=18.0,
                precision=0.2,
                recall=0.5,
                rr=0.5,
                ndcg=0.6,
            ),
        ),
        mean_precision=0.3,
        mean_recall=0.6,
        mrr=0.75,
        mean_ndcg=0.7,
        total_duration_ms=26.0,
        embedding_model="model-b",
    )

    comparison = compare_evaluation_runs(first=first, second=second)

    assert comparison.same_retrieval_configuration is False
    assert comparison.same_case_set is True
    assert comparison.aggregate_comparable is True
    assert comparison.shared_case_count == 2
    assert comparison.comparable_case_count == 2
    assert comparison.mean_precision_delta == pytest.approx(0.05)
    assert comparison.mean_recall_delta == pytest.approx(0.05)
    assert comparison.mrr_delta == pytest.approx(0.25)
    assert comparison.mean_ndcg_delta == pytest.approx(0.05)
    assert comparison.total_duration_delta_ms == -4.0

    first_case = next(
        case for case in comparison.cases if case.case_id == first_case_id
    )
    assert first_case.presence is EvaluationRunCasePresence.BOTH
    assert first_case.comparable is True
    assert first_case.precision_delta == pytest.approx(0.2)
    assert first_case.reciprocal_rank_delta == pytest.approx(0.5)
    assert first_case.ndcg_delta == pytest.approx(0.2)
    assert first_case.duration_delta_ms == -2.0


def test_run_comparison_suppresses_deltas_when_case_set_changed() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    shared_id = uuid4()
    new_id = uuid4()

    first = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        cases=(
            _case(
                case_id=shared_id,
                position=1,
                query="shared",
                duration_ms=4.0,
                precision=0.2,
                recall=0.5,
                rr=1.0,
                ndcg=0.7,
            ),
        ),
        mean_precision=0.2,
        mean_recall=0.5,
        mrr=1.0,
        mean_ndcg=0.7,
        total_duration_ms=4.0,
    )
    second = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        cases=(
            _case(
                case_id=shared_id,
                position=1,
                query="shared",
                duration_ms=3.0,
                precision=0.3,
                recall=0.6,
                rr=1.0,
                ndcg=0.8,
            ),
            _case(
                case_id=new_id,
                position=2,
                query="new query",
                duration_ms=5.0,
                precision=0.4,
                recall=0.7,
                rr=0.5,
                ndcg=0.6,
            ),
        ),
        mean_precision=0.35,
        mean_recall=0.65,
        mrr=0.75,
        mean_ndcg=0.7,
        total_duration_ms=8.0,
    )

    comparison = compare_evaluation_runs(first=first, second=second)

    assert comparison.same_case_set is False
    assert comparison.aggregate_comparable is False
    assert comparison.first_only_case_count == 0
    assert comparison.second_only_case_count == 1
    assert comparison.mean_precision_delta is None
    assert comparison.mrr_delta is None

    second_only = next(
        case for case in comparison.cases if case.case_id == new_id
    )
    assert second_only.presence is EvaluationRunCasePresence.SECOND_ONLY
    assert second_only.comparable is False
    assert second_only.precision_delta is None


def test_run_comparison_suppresses_case_and_aggregate_deltas_when_query_changed() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    case_id = uuid4()

    first = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        cases=(
            _case(
                case_id=case_id,
                position=1,
                query="old query",
                duration_ms=4.0,
                precision=0.2,
                recall=0.5,
                rr=1.0,
                ndcg=0.7,
            ),
        ),
        mean_precision=0.2,
        mean_recall=0.5,
        mrr=1.0,
        mean_ndcg=0.7,
        total_duration_ms=4.0,
    )
    second = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        cases=(
            _case(
                case_id=case_id,
                position=1,
                query="changed query",
                duration_ms=3.0,
                precision=0.5,
                recall=1.0,
                rr=1.0,
                ndcg=1.0,
            ),
        ),
        mean_precision=0.5,
        mean_recall=1.0,
        mrr=1.0,
        mean_ndcg=1.0,
        total_duration_ms=3.0,
    )

    comparison = compare_evaluation_runs(first=first, second=second)

    assert comparison.same_case_set is True
    assert comparison.query_changed_case_count == 1
    assert comparison.aggregate_comparable is False
    assert comparison.mean_ndcg_delta is None
    assert comparison.cases[0].query_changed is True
    assert comparison.cases[0].comparable is False
    assert comparison.cases[0].ndcg_delta is None


class FakeRunReader:
    def __init__(self, runs: tuple[EvaluationRun, ...]) -> None:
        self._runs = {run.id: run for run in runs}

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        return self._runs[run_id]


def test_run_comparison_service_rejects_same_run_id() -> None:
    service = EvaluationRunComparisonService(FakeRunReader(()))
    run_id = uuid4()

    with pytest.raises(EvaluationRunComparisonQueryError):
        asyncio.run(
            service.compare(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                first_run_id=run_id,
                second_run_id=run_id,
            )
        )
