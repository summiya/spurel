from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.dependencies import get_evaluation_dataset_service
from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetPersistenceError
from spurel.evaluation_datasets.service import EvaluationDatasetNotFoundError
from spurel.main import create_app
from spurel.retrieval.evaluation import RelevanceJudgment


class FakeEvaluationDatasetService:
    def __init__(self) -> None:
        self.dataset: EvaluationDataset | None = None
        self.datasets: tuple[EvaluationDatasetSummary, ...] = ()
        self.case: EvaluationCase | None = None
        self.cases: tuple[EvaluationCaseSummary, ...] = ()
        self.error: Exception | None = None

    async def create_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        name: str,
    ) -> EvaluationDataset:
        if self.error is not None:
            raise self.error
        if self.dataset is not None:
            return self.dataset
        return EvaluationDataset(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            name=name.strip(),
            created_at=datetime.now(UTC),
        )

    async def list_datasets(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ):
        if self.error is not None:
            raise self.error
        return self.datasets

    async def add_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        query: str,
        judgments: tuple[RelevanceJudgment, ...],
    ) -> EvaluationCase:
        if self.error is not None:
            raise self.error
        if self.case is not None:
            return self.case
        return EvaluationCase(
            id=uuid4(),
            dataset_id=dataset_id,
            query=query.strip(),
            judgments=judgments,
            created_at=datetime.now(UTC),
        )

    async def list_cases(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ):
        if self.error is not None:
            raise self.error
        return self.cases

    async def get_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase:
        if self.error is not None:
            raise self.error
        assert self.case is not None
        return self.case


def _client(service: FakeEvaluationDatasetService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_evaluation_dataset_service] = lambda: service
    return TestClient(application)


def test_create_evaluation_dataset_returns_public_resource() -> None:
    knowledge_base_id = uuid4()
    service = FakeEvaluationDatasetService()
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets",
        json={"name": " Baseline retrieval set "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["knowledge_base_id"] == str(knowledge_base_id)
    assert body["name"] == "Baseline retrieval set"
    assert body["case_count"] == 0


def test_create_case_returns_persisted_judgments() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    relevant_chunk = uuid4()
    service = FakeEvaluationDatasetService()
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/cases",
        json={
            "query": "authentication architecture",
            "judgments": [
                {
                    "chunk_id": str(relevant_chunk),
                    "relevance": 3,
                }
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["dataset_id"] == str(dataset_id)
    assert body["query"] == "authentication architecture"
    assert body["judgments"] == [
        {
            "chunk_id": str(relevant_chunk),
            "relevance": 3,
        }
    ]


def test_list_cases_returns_summaries_without_loading_judgments() -> None:
    dataset_id = uuid4()
    service = FakeEvaluationDatasetService()
    service.cases = (
        EvaluationCaseSummary(
            id=uuid4(),
            dataset_id=dataset_id,
            query="query",
            judgment_count=5,
            relevant_judgment_count=2,
            created_at=datetime.now(UTC),
        ),
    )
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{dataset_id}/cases"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["judgment_count"] == 5
    assert body["items"][0]["relevant_judgment_count"] == 2
    assert "judgments" not in body["items"][0]


def test_dataset_scope_failure_returns_not_found() -> None:
    service = FakeEvaluationDatasetService()
    service.error = EvaluationDatasetNotFoundError("internal scope detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/cases",
        json={
            "query": "query",
            "judgments": [
                {
                    "chunk_id": str(uuid4()),
                    "relevance": 1,
                }
            ],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation dataset was not found"}
    assert "internal scope detail" not in response.text


def test_dataset_persistence_errors_are_hidden() -> None:
    service = FakeEvaluationDatasetService()
    service.error = EvaluationDatasetPersistenceError("database secret detail")
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation dataset service temporarily unavailable"
    }
    assert "database secret detail" not in response.text


def test_dataset_list_bounds_page_size() -> None:
    client = _client(FakeEvaluationDatasetService())

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets",
        params={"limit": 101},
    )

    assert response.status_code == 422
