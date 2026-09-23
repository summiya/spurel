from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.dependencies import get_evaluation_run_service
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationCaseResult,
    DatasetEvaluationMode,
    DatasetEvaluationResult,
)
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError
from spurel.evaluation_datasets.run_service import EvaluationRunNotFoundError
from spurel.main import create_app
from spurel.retrieval.evaluation import RetrievalMetricValues


class FakeEvaluationRunService:
    def __init__(self) -> None:
        self.runs: tuple[EvaluationRunSummary, ...] = ()
        self.run: EvaluationRun | None = None
        self.error: Exception | None = None
        self.last_list_call: dict[str, object] | None = None
        self.last_get_call: dict[str, object] | None = None

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationRunSummary]:
        self.last_list_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "limit": limit,
            "offset": offset,
        }
        if self.error is not None:
            raise self.error
        return self.runs

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        self.last_get_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "run_id": run_id,
        }
        if self.error is not None:
            raise self.error
        assert self.run is not None
        return self.run


def _run(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
) -> EvaluationRun:
    metrics = RetrievalMetricValues(
        cutoff=10,
        judged_count=4,
        relevant_count=2,
        retrieved_count_at_k=10,
        judged_retrieved_at_k=4,
        relevant_retrieved_at_k=2,
        judgment_coverage_at_k=0.4,
        precision_at_k=0.2,
        recall_at_k=1.0,
        reciprocal_rank_at_k=0.5,
        ndcg_at_k=0.8,
    )
    execution = DatasetEvaluationResult(
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        case_count=1,
        total_duration_ms=6.0,
        mean_duration_ms=6.0,
        judgment_coverage_case_count=1,
        mean_judgment_coverage_at_k=0.4,
        mean_precision_at_k=0.2,
        mean_recall_at_k=1.0,
        mrr_at_k=0.5,
        mean_ndcg_at_k=0.8,
        cases=(
            DatasetEvaluationCaseResult(
                case_id=uuid4(),
                query="authentication",
                duration_ms=6.0,
                metrics=metrics,
            ),
        ),
    )
    return EvaluationRun.from_execution(
        knowledge_base_id=knowledge_base_id,
        result=execution,
    )


def _summary(run: EvaluationRun) -> EvaluationRunSummary:
    return EvaluationRunSummary(
        id=run.id,
        knowledge_base_id=run.knowledge_base_id,
        dataset_id=run.dataset_id,
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


def _client(service: FakeEvaluationRunService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_evaluation_run_service] = lambda: service
    return TestClient(application)


def test_run_history_returns_lightweight_summaries() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
    )
    service = FakeEvaluationRunService()
    service.runs = (_summary(run),)
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/runs",
        params={"limit": 25, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["items"][0]["run_id"] == str(run.id)
    assert body["items"][0]["mrr_at_k"] == 0.5
    assert "cases" not in body["items"][0]
    assert service.last_list_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "limit": 25,
        "offset": 0,
    }


def test_run_detail_returns_complete_per_case_snapshot() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
    )
    service = FakeEvaluationRunService()
    service.run = run
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/runs/{run.id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(run.id)
    assert body["knowledge_base_id"] == str(knowledge_base_id)
    assert body["cases"][0]["position"] == 1
    assert body["cases"][0]["query"] == "authentication"
    assert body["cases"][0]["ndcg_at_k"] == 0.8


def test_run_detail_returns_scoped_not_found() -> None:
    service = FakeEvaluationRunService()
    service.error = EvaluationRunNotFoundError("cross-scope internals")
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/runs/{uuid4()}"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation run was not found"}
    assert "cross-scope internals" not in response.text


def test_run_history_hides_database_errors() -> None:
    service = FakeEvaluationRunService()
    service.error = EvaluationRunPersistenceError("database secret detail")
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/runs"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "evaluation run history temporarily unavailable"
    }
    assert "database secret detail" not in response.text


def test_run_history_bounds_page_size() -> None:
    client = _client(FakeEvaluationRunService())

    response = client.get(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/runs",
        params={"limit": 101},
    )

    assert response.status_code == 422
