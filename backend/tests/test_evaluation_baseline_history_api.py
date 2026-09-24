from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaselineConfiguration,
    EvaluationBaselinePromotion,
)
from spurel.evaluation_datasets.baseline_ports import (
    EvaluationBaselinePersistenceError,
)
from spurel.evaluation_datasets.dependencies import (
    get_evaluation_baseline_service,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.main import create_app


class FakeEvaluationBaselineHistoryService:
    def __init__(self) -> None:
        self.items: tuple[EvaluationBaselinePromotion, ...] = ()
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def list_history_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ):
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "limit": limit,
            "offset": offset,
        }
        if self.error is not None:
            raise self.error
        return self.items


def _promotion(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    run_id: UUID,
) -> EvaluationBaselinePromotion:
    configuration = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.VECTOR,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )
    return EvaluationBaselinePromotion(
        id=uuid4(),
        baseline_id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
        configuration=configuration,
        configuration_fingerprint=configuration.fingerprint,
        promoted_at=datetime.now(UTC),
    )


def _client(service: FakeEvaluationBaselineHistoryService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_evaluation_baseline_service
    ] = lambda: service
    return TestClient(application)


def test_baseline_history_returns_append_only_promotion_snapshots() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run_id = uuid4()
    promotion = _promotion(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )
    service = FakeEvaluationBaselineHistoryService()
    service.items = (promotion,)
    client = _client(service)

    response = client.get(
        (
            f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/"
            f"{dataset_id}/baselines/history"
        ),
        params={"limit": 25, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["items"][0]["promotion_id"] == str(promotion.id)
    assert body["items"][0]["baseline_id"] == str(promotion.baseline_id)
    assert body["items"][0]["run_id"] == str(run_id)
    assert body["items"][0]["mode"] == "vector"
    assert body["items"][0]["embedding_dimensions"] == 1536
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "limit": 25,
        "offset": 0,
    }


def test_baseline_history_bounds_page_size() -> None:
    client = _client(FakeEvaluationBaselineHistoryService())

    response = client.get(
        (
            f"/knowledge-bases/{uuid4()}/evaluation-datasets/"
            f"{uuid4()}/baselines/history"
        ),
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_baseline_history_hides_persistence_errors() -> None:
    service = FakeEvaluationBaselineHistoryService()
    service.error = EvaluationBaselinePersistenceError(
        "database secret detail"
    )
    client = _client(service)

    response = client.get(
        (
            f"/knowledge-bases/{uuid4()}/evaluation-datasets/"
            f"{uuid4()}/baselines/history"
        )
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation baseline service temporarily unavailable"
    }
    assert "database secret detail" not in response.text
