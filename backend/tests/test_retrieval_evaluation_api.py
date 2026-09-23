from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import get_retrieval_evaluation_service
from spurel.retrieval.evaluation import (
    RelevanceJudgment,
    RetrievalEvaluation,
    RetrievalEvaluationQueryError,
)
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.trace_service import RetrievalTraceNotFoundError


class FakeRetrievalEvaluationService:
    def __init__(self) -> None:
        self.result: RetrievalEvaluation | None = None
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def evaluate(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
        cutoff: int,
        judgments: tuple[RelevanceJudgment, ...],
    ) -> RetrievalEvaluation:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "trace_id": trace_id,
            "cutoff": cutoff,
            "judgments": judgments,
        }
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeRetrievalEvaluationService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_retrieval_evaluation_service
    ] = lambda: service
    return TestClient(application)


def test_retrieval_evaluation_returns_deterministic_metrics() -> None:
    knowledge_base_id = uuid4()
    trace_id = uuid4()
    relevant_chunk = uuid4()
    service = FakeRetrievalEvaluationService()
    service.result = RetrievalEvaluation(
        trace_id=trace_id,
        cutoff=5,
        judged_count=8,
        relevant_count=4,
        retrieved_count_at_k=5,
        judged_retrieved_at_k=4,
        relevant_retrieved_at_k=3,
        judgment_coverage_at_k=0.8,
        precision_at_k=0.6,
        recall_at_k=0.75,
        reciprocal_rank_at_k=0.5,
        ndcg_at_k=0.82,
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/traces/{trace_id}/evaluation",
        json={
            "cutoff": 5,
            "judgments": [
                {
                    "chunk_id": str(relevant_chunk),
                    "relevance": 3,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "trace_id": str(trace_id),
        "cutoff": 5,
        "judged_count": 8,
        "relevant_count": 4,
        "retrieved_count_at_k": 5,
        "judged_retrieved_at_k": 4,
        "relevant_retrieved_at_k": 3,
        "judgment_coverage_at_k": 0.8,
        "precision_at_k": 0.6,
        "recall_at_k": 0.75,
        "reciprocal_rank_at_k": 0.5,
        "ndcg_at_k": 0.82,
    }

    assert service.last_call is not None
    assert service.last_call["knowledge_base_id"] == knowledge_base_id
    assert service.last_call["trace_id"] == trace_id
    assert service.last_call["cutoff"] == 5
    judgments = service.last_call["judgments"]
    assert len(judgments) == 1
    assert judgments[0].chunk_id == relevant_chunk
    assert judgments[0].relevance == 3


def test_retrieval_evaluation_rejects_invalid_relevance_grade() -> None:
    client = _client(FakeRetrievalEvaluationService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}/evaluation",
        json={
            "cutoff": 5,
            "judgments": [
                {
                    "chunk_id": str(uuid4()),
                    "relevance": 4,
                }
            ],
        },
    )

    assert response.status_code == 422


def test_retrieval_evaluation_hides_duplicate_judgment_details() -> None:
    service = FakeRetrievalEvaluationService()
    service.error = RetrievalEvaluationQueryError(
        "duplicate historical chunk labels"
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}/evaluation",
        json={
            "cutoff": 5,
            "judgments": [
                {
                    "chunk_id": str(uuid4()),
                    "relevance": 1,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "retrieval evaluation request is invalid"
    }
    assert "duplicate historical chunk labels" not in response.text


def test_retrieval_evaluation_returns_scoped_not_found() -> None:
    service = FakeRetrievalEvaluationService()
    service.error = RetrievalTraceNotFoundError("cross-knowledge-base detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}/evaluation",
        json={
            "cutoff": 5,
            "judgments": [
                {
                    "chunk_id": str(uuid4()),
                    "relevance": 1,
                }
            ],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "retrieval trace was not found"}
    assert "cross-knowledge-base detail" not in response.text


def test_retrieval_evaluation_hides_trace_storage_errors() -> None:
    service = FakeRetrievalEvaluationService()
    service.error = RetrievalTracePersistenceError("database secret detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}/evaluation",
        json={
            "cutoff": 5,
            "judgments": [
                {
                    "chunk_id": str(uuid4()),
                    "relevance": 1,
                }
            ],
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval evaluation temporarily unavailable"
    }
    assert "database secret detail" not in response.text
