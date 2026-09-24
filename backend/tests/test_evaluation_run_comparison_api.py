from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.dependencies import (
    get_evaluation_run_comparison_service,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_comparison import (
    EvaluationRunComparison,
    EvaluationRunComparisonSide,
    EvaluationRunCaseComparison,
    EvaluationRunCasePresence,
)
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError
from spurel.evaluation_datasets.run_service import EvaluationRunNotFoundError
from spurel.main import create_app


class FakeEvaluationRunComparisonService:
    def __init__(self) -> None:
        self.result: EvaluationRunComparison | None = None
        self.error: Exception | None = None
        self.last_call: dict[str, UUID] | None = None

    async def compare(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        first_run_id: UUID,
        second_run_id: UUID,
    ) -> EvaluationRunComparison:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "first_run_id": first_run_id,
            "second_run_id": second_run_id,
        }
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _side(
    *,
    run_id: UUID,
    mode: DatasetEvaluationMode,
    precision: float,
    ndcg: float,
) -> EvaluationRunComparisonSide:
    uses_embeddings = mode is not DatasetEvaluationMode.KEYWORD
    return EvaluationRunComparisonSide(
        run_id=run_id,
        mode=mode,
        top_k=10,
        candidate_k=50 if mode is DatasetEvaluationMode.HYBRID else None,
        rrf_k=60 if mode is DatasetEvaluationMode.HYBRID else None,
        embedding_provider="openai" if uses_embeddings else None,
        embedding_model="model" if uses_embeddings else None,
        embedding_dimensions=1536 if uses_embeddings else None,
        case_count=1,
        total_duration_ms=10.0,
        mean_duration_ms=10.0,
        judgment_coverage_case_count=1,
        mean_judgment_coverage_at_k=0.5,
        mean_precision_at_k=precision,
        mean_recall_at_k=1.0,
        mrr_at_k=0.5,
        mean_ndcg_at_k=ndcg,
        created_at=datetime.now(UTC),
    )


def _comparison(
    *,
    dataset_id: UUID,
    first_run_id: UUID,
    second_run_id: UUID,
) -> EvaluationRunComparison:
    case_id = uuid4()
    return EvaluationRunComparison(
        dataset_id=dataset_id,
        first=_side(
            run_id=first_run_id,
            mode=DatasetEvaluationMode.VECTOR,
            precision=0.2,
            ndcg=0.7,
        ),
        second=_side(
            run_id=second_run_id,
            mode=DatasetEvaluationMode.HYBRID,
            precision=0.3,
            ndcg=0.8,
        ),
        same_retrieval_configuration=False,
        same_case_set=True,
        aggregate_comparable=True,
        shared_case_count=1,
        first_only_case_count=0,
        second_only_case_count=0,
        comparable_case_count=1,
        query_changed_case_count=0,
        total_duration_delta_ms=-2.0,
        mean_duration_delta_ms=-2.0,
        mean_judgment_coverage_delta=0.0,
        mean_precision_delta=0.1,
        mean_recall_delta=0.0,
        mrr_delta=0.0,
        mean_ndcg_delta=0.1,
        cases=(
            EvaluationRunCaseComparison(
                case_id=case_id,
                presence=EvaluationRunCasePresence.BOTH,
                first_position=1,
                second_position=1,
                first_query="authentication",
                second_query="authentication",
                query_changed=False,
                comparable=True,
                first_duration_ms=10.0,
                second_duration_ms=8.0,
                duration_delta_ms=-2.0,
                first_precision_at_k=0.2,
                second_precision_at_k=0.3,
                precision_delta=0.1,
                first_recall_at_k=1.0,
                second_recall_at_k=1.0,
                recall_delta=0.0,
                first_reciprocal_rank_at_k=0.5,
                second_reciprocal_rank_at_k=0.5,
                reciprocal_rank_delta=0.0,
                first_ndcg_at_k=0.7,
                second_ndcg_at_k=0.8,
                ndcg_delta=0.1,
            ),
        ),
    )


def _client(service: FakeEvaluationRunComparisonService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_evaluation_run_comparison_service
    ] = lambda: service
    return TestClient(application)


def test_run_comparison_returns_aggregate_and_case_deltas() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    first_run_id = uuid4()
    second_run_id = uuid4()
    service = FakeEvaluationRunComparisonService()
    service.result = _comparison(
        dataset_id=dataset_id,
        first_run_id=first_run_id,
        second_run_id=second_run_id,
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/run-comparisons",
        json={
            "first_run_id": str(first_run_id),
            "second_run_id": str(second_run_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == str(dataset_id)
    assert body["first"]["mode"] == "vector"
    assert body["second"]["mode"] == "hybrid"
    assert body["same_retrieval_configuration"] is False
    assert body["aggregate_comparable"] is True
    assert body["mean_precision_delta"] == 0.1
    assert body["mean_ndcg_delta"] == 0.1
    assert body["cases"][0]["presence"] == "both"
    assert body["cases"][0]["precision_delta"] == 0.1
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "first_run_id": first_run_id,
        "second_run_id": second_run_id,
    }


def test_run_comparison_rejects_same_run_id_at_http_boundary() -> None:
    run_id = uuid4()
    client = _client(FakeEvaluationRunComparisonService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/run-comparisons",
        json={
            "first_run_id": str(run_id),
            "second_run_id": str(run_id),
        },
    )

    assert response.status_code == 422


def test_run_comparison_returns_scoped_not_found() -> None:
    service = FakeEvaluationRunComparisonService()
    service.error = EvaluationRunNotFoundError("cross-scope internals")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/run-comparisons",
        json={
            "first_run_id": str(uuid4()),
            "second_run_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation run was not found"}
    assert "cross-scope internals" not in response.text


def test_run_comparison_hides_persistence_errors() -> None:
    service = FakeEvaluationRunComparisonService()
    service.error = EvaluationRunPersistenceError("database secret detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/run-comparisons",
        json={
            "first_run_id": str(uuid4()),
            "second_run_id": str(uuid4()),
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation run comparison temporarily unavailable"
    }
    assert "database secret detail" not in response.text
