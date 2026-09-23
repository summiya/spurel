from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.evaluation_datasets.dependencies import (
    get_hybrid_dataset_evaluation_service,
    get_keyword_dataset_evaluation_service,
    get_vector_dataset_evaluation_service,
)
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationCaseResult,
    DatasetEvaluationLimitError,
    DatasetEvaluationMode,
    DatasetEvaluationResult,
)
from spurel.evaluation_datasets.service import EvaluationDatasetNotFoundError
from spurel.main import create_app
from spurel.retrieval.evaluation import RetrievalMetricValues


class FakeDatasetEvaluationService:
    def __init__(self, result: DatasetEvaluationResult | None = None) -> None:
        self.result = result
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        top_k: int,
        candidate_k: int | None = None,
        rrf_k: int | None = None,
    ) -> DatasetEvaluationResult:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "rrf_k": rrf_k,
        }
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _result(
    *,
    dataset_id: UUID,
    mode: DatasetEvaluationMode,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
) -> DatasetEvaluationResult:
    metrics = RetrievalMetricValues(
        cutoff=10,
        judged_count=3,
        relevant_count=2,
        retrieved_count_at_k=10,
        judged_retrieved_at_k=3,
        relevant_retrieved_at_k=2,
        judgment_coverage_at_k=0.3,
        precision_at_k=0.2,
        recall_at_k=1.0,
        reciprocal_rank_at_k=0.5,
        ndcg_at_k=0.75,
    )
    case = DatasetEvaluationCaseResult(
        case_id=uuid4(),
        query="authentication",
        duration_ms=4.0,
        metrics=metrics,
    )
    uses_embeddings = mode is not DatasetEvaluationMode.KEYWORD
    return DatasetEvaluationResult(
        dataset_id=dataset_id,
        mode=mode,
        top_k=10,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        embedding_provider="openai" if uses_embeddings else None,
        embedding_model="model" if uses_embeddings else None,
        embedding_dimensions=1536 if uses_embeddings else None,
        case_count=1,
        total_duration_ms=4.0,
        mean_duration_ms=4.0,
        mean_judgment_coverage_at_k=0.3,
        mean_precision_at_k=0.2,
        mean_recall_at_k=1.0,
        mrr_at_k=0.5,
        mean_ndcg_at_k=0.75,
        cases=(case,),
    )


def _client(
    *,
    vector: FakeDatasetEvaluationService | None = None,
    keyword: FakeDatasetEvaluationService | None = None,
    hybrid: FakeDatasetEvaluationService | None = None,
) -> TestClient:
    application = create_app()
    if vector is not None:
        application.dependency_overrides[
            get_vector_dataset_evaluation_service
        ] = lambda: vector
    if keyword is not None:
        application.dependency_overrides[
            get_keyword_dataset_evaluation_service
        ] = lambda: keyword
    if hybrid is not None:
        application.dependency_overrides[
            get_hybrid_dataset_evaluation_service
        ] = lambda: hybrid
    return TestClient(application)


def test_keyword_dataset_evaluation_returns_aggregate_and_case_metrics() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    service = FakeDatasetEvaluationService(
        _result(dataset_id=dataset_id, mode=DatasetEvaluationMode.KEYWORD)
    )
    client = _client(keyword=service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/evaluate/keyword",
        json={"top_k": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == str(dataset_id)
    assert body["mode"] == "keyword"
    assert body["mrr_at_k"] == 0.5
    assert body["mean_precision_at_k"] == 0.2
    assert body["mean_recall_at_k"] == 1.0
    assert body["cases"][0]["reciprocal_rank_at_k"] == 0.5
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "top_k": 10,
        "candidate_k": None,
        "rrf_k": None,
    }


def test_hybrid_dataset_evaluation_preserves_fusion_configuration() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    service = FakeDatasetEvaluationService(
        _result(
            dataset_id=dataset_id,
            mode=DatasetEvaluationMode.HYBRID,
            candidate_k=50,
            rrf_k=60,
        )
    )
    client = _client(hybrid=service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/evaluate/hybrid",
        json={
            "top_k": 10,
            "candidate_k": 50,
            "rrf_k": 60,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hybrid"
    assert body["candidate_k"] == 50
    assert body["rrf_k"] == 60
    assert body["embedding_provider"] == "openai"


def test_hybrid_dataset_evaluation_rejects_small_candidate_pool() -> None:
    client = _client(
        hybrid=FakeDatasetEvaluationService()
    )

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/evaluate/hybrid",
        json={
            "top_k": 20,
            "candidate_k": 10,
            "rrf_k": 60,
        },
    )

    assert response.status_code == 422


def test_dataset_evaluation_returns_scoped_not_found() -> None:
    service = FakeDatasetEvaluationService()
    service.error = EvaluationDatasetNotFoundError("internal scope detail")
    client = _client(keyword=service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/evaluate/keyword",
        json={"top_k": 10},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "evaluation dataset was not found"}
    assert "internal scope detail" not in response.text


def test_dataset_evaluation_hides_synchronous_size_limit_details() -> None:
    service = FakeDatasetEvaluationService()
    service.error = DatasetEvaluationLimitError("50,001 labels found")
    client = _client(keyword=service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{uuid4()}/evaluate/keyword",
        json={"top_k": 10},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "dataset evaluation request is invalid"}
    assert "50,001 labels found" not in response.text


def test_vector_dataset_evaluation_returns_embedding_configuration() -> None:
    dataset_id = uuid4()
    service = FakeDatasetEvaluationService(
        _result(dataset_id=dataset_id, mode=DatasetEvaluationMode.VECTOR)
    )
    client = _client(vector=service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/evaluation-datasets/{dataset_id}/evaluate/vector",
        json={"top_k": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "vector"
    assert body["embedding_model"] == "model"
    assert body["embedding_dimensions"] == 1536
