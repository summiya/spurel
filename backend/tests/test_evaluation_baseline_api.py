from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselineConfigurationError,
)
from spurel.evaluation_datasets.baseline_ports import (
    EvaluationBaselinePersistenceError,
)
from spurel.evaluation_datasets.baseline_service import (
    EvaluationBaselineNotFoundError,
)
from spurel.evaluation_datasets.dependencies import (
    get_evaluation_baseline_service,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_service import EvaluationRunNotFoundError
from spurel.main import create_app


class FakeEvaluationBaselineService:
    def __init__(self) -> None:
        self.baseline: EvaluationBaseline | None = None
        self.items: tuple[EvaluationBaseline, ...] = ()
        self.error: Exception | None = None
        self.last_promote: dict[str, UUID] | None = None
        self.last_resolve: dict[str, object] | None = None

    async def promote(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationBaseline:
        self.last_promote = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "run_id": run_id,
        }
        if self.error is not None:
            raise self.error
        assert self.baseline is not None
        return self.baseline

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ):
        if self.error is not None:
            raise self.error
        return self.items

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline:
        self.last_resolve = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "configuration": configuration,
        }
        if self.error is not None:
            raise self.error
        assert self.baseline is not None
        return self.baseline


def _baseline(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    run_id: UUID,
) -> EvaluationBaseline:
    configuration = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.VECTOR,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )
    return EvaluationBaseline(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
        configuration=configuration,
        configuration_fingerprint=configuration.fingerprint,
        promoted_at=datetime.now(UTC),
    )


def _client(service: FakeEvaluationBaselineService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_evaluation_baseline_service
    ] = lambda: service
    return TestClient(application)


def test_promote_baseline_returns_exact_run_configuration() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run_id = uuid4()
    service = FakeEvaluationBaselineService()
    service.baseline = _baseline(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )
    client = _client(service)

    response = client.put(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/baselines",
        json={"run_id": str(run_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(run_id)
    assert body["mode"] == "vector"
    assert body["top_k"] == 10
    assert body["embedding_model"] == "model-a"
    assert len(body["configuration_fingerprint"]) == 64
    assert service.last_promote == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "run_id": run_id,
    }


def test_resolve_baseline_uses_exact_configuration() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run_id = uuid4()
    service = FakeEvaluationBaselineService()
    service.baseline = _baseline(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/baselines/resolve",
        json={
            "mode": "vector",
            "top_k": 10,
            "embedding_provider": "openai",
            "embedding_model": "model-a",
            "embedding_dimensions": 1536,
        },
    )

    assert response.status_code == 200
    assert service.last_resolve is not None
    configuration = service.last_resolve["configuration"]
    assert configuration.mode is DatasetEvaluationMode.VECTOR
    assert configuration.top_k == 10
    assert configuration.embedding_model == "model-a"


def test_resolve_invalid_configuration_returns_generic_422() -> None:
    service = FakeEvaluationBaselineService()
    service.error = EvaluationBaselineConfigurationError("internal detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/baselines/resolve",
        json={
            "mode": "keyword",
            "top_k": 10,
            "embedding_provider": "openai",
            "embedding_model": "model-a",
            "embedding_dimensions": 1536,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "evaluation baseline configuration is invalid"
    }
    assert "internal detail" not in response.text


def test_promote_cross_scope_run_returns_not_found() -> None:
    service = FakeEvaluationBaselineService()
    service.error = EvaluationRunNotFoundError("cross-scope internals")
    client = _client(service)

    response = client.put(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/baselines",
        json={"run_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation run was not found"}
    assert "cross-scope internals" not in response.text


def test_resolve_missing_baseline_returns_not_found() -> None:
    service = FakeEvaluationBaselineService()
    service.error = EvaluationBaselineNotFoundError("missing internals")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/baselines/resolve",
        json={
            "mode": "keyword",
            "top_k": 10,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation baseline was not found"}
    assert "missing internals" not in response.text


def test_list_baselines_bounds_page_size() -> None:
    client = _client(FakeEvaluationBaselineService())

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/baselines",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_baseline_persistence_errors_are_hidden() -> None:
    service = FakeEvaluationBaselineService()
    service.error = EvaluationBaselinePersistenceError("database secret detail")
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/baselines"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation baseline service temporarily unavailable"
    }
    assert "database secret detail" not in response.text
