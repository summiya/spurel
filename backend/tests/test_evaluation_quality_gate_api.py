from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.dependencies import (
    get_evaluation_quality_gate_service,
)
from spurel.evaluation_datasets.quality_gate import (
    EvaluationQualityGateCheck,
    EvaluationQualityGateMetric,
    EvaluationQualityGateRegressionKind,
    EvaluationQualityGateResult,
    EvaluationQualityGateStatus,
    EvaluationQualityGateThresholds,
)
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError
from spurel.evaluation_datasets.run_service import EvaluationRunNotFoundError
from spurel.main import create_app


class FakeEvaluationQualityGateService:
    def __init__(self) -> None:
        self.result: EvaluationQualityGateResult | None = None
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def evaluate(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        first_run_id: UUID,
        second_run_id: UUID,
        thresholds: EvaluationQualityGateThresholds,
    ) -> EvaluationQualityGateResult:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "first_run_id": first_run_id,
            "second_run_id": second_run_id,
            "thresholds": thresholds,
        }
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeEvaluationQualityGateService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_evaluation_quality_gate_service
    ] = lambda: service
    return TestClient(application)


def test_quality_gate_api_returns_threshold_evidence() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    first_run_id = uuid4()
    second_run_id = uuid4()
    service = FakeEvaluationQualityGateService()
    service.result = EvaluationQualityGateResult(
        status=EvaluationQualityGateStatus.FAIL,
        aggregate_comparable=True,
        same_retrieval_configuration=False,
        unavailable_metrics=(),
        checks=(
            EvaluationQualityGateCheck(
                metric=EvaluationQualityGateMetric.MRR_AT_K,
                regression_kind=EvaluationQualityGateRegressionKind.DROP,
                first_value=0.8,
                second_value=0.74,
                delta=-0.06,
                allowed_regression=0.03,
                regression_amount=0.06,
                passed=False,
            ),
        ),
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/quality-gates/evaluate",
        json={
            "first_run_id": str(first_run_id),
            "second_run_id": str(second_run_id),
            "thresholds": {
                "max_mrr_drop": 0.03,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == str(dataset_id)
    assert body["first_run_id"] == str(first_run_id)
    assert body["second_run_id"] == str(second_run_id)
    assert body["status"] == "fail"
    assert body["aggregate_comparable"] is True
    assert body["same_retrieval_configuration"] is False
    assert body["thresholds"]["max_mrr_drop"] == 0.03
    assert body["unavailable_metrics"] == []
    assert body["checks"] == [
        {
            "metric": "mrr_at_k",
            "regression_kind": "drop",
            "first_value": 0.8,
            "second_value": 0.74,
            "delta": -0.06,
            "allowed_regression": 0.03,
            "regression_amount": 0.06,
            "passed": False,
        }
    ]

    assert service.last_call is not None
    thresholds = service.last_call["thresholds"]
    assert isinstance(thresholds, EvaluationQualityGateThresholds)
    assert thresholds.max_mrr_drop == 0.03


def test_quality_gate_api_rejects_empty_threshold_configuration() -> None:
    client = _client(FakeEvaluationQualityGateService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/quality-gates/evaluate",
        json={
            "first_run_id": str(uuid4()),
            "second_run_id": str(uuid4()),
            "thresholds": {},
        },
    )

    assert response.status_code == 422


def test_quality_gate_api_rejects_same_run_ids() -> None:
    run_id = uuid4()
    client = _client(FakeEvaluationQualityGateService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/quality-gates/evaluate",
        json={
            "first_run_id": str(run_id),
            "second_run_id": str(run_id),
            "thresholds": {
                "max_mean_ndcg_drop": 0.02,
            },
        },
    )

    assert response.status_code == 422


def test_quality_gate_api_returns_scoped_not_found() -> None:
    service = FakeEvaluationQualityGateService()
    service.error = EvaluationRunNotFoundError("cross-scope internal detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/quality-gates/evaluate",
        json={
            "first_run_id": str(uuid4()),
            "second_run_id": str(uuid4()),
            "thresholds": {
                "max_mean_recall_drop": 0.02,
            },
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation run was not found"}
    assert "cross-scope internal detail" not in response.text


def test_quality_gate_api_hides_persistence_errors() -> None:
    service = FakeEvaluationQualityGateService()
    service.error = EvaluationRunPersistenceError("database secret detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/quality-gates/evaluate",
        json={
            "first_run_id": str(uuid4()),
            "second_run_id": str(uuid4()),
            "thresholds": {
                "max_mean_duration_increase_ms": 50,
            },
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation quality gate temporarily unavailable"
    }
    assert "database secret detail" not in response.text
