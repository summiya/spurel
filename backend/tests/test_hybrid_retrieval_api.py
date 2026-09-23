from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import get_hybrid_retrieval_service
from spurel.retrieval.hybrid import HybridRetrievalMatch, HybridRetrievalResultError


class FakeHybridRetrievalService:
    def __init__(self) -> None:
        self.results: Sequence[HybridRetrievalMatch] = ()
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
        candidate_limit: int,
        rrf_k: int,
    ) -> Sequence[HybridRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
            "candidate_limit": candidate_limit,
            "rrf_k": rrf_k,
        }
        if self.error is not None:
            raise self.error
        return self.results


def _client(service: FakeHybridRetrievalService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_hybrid_retrieval_service] = lambda: service
    return TestClient(application)


def test_hybrid_retrieval_returns_fused_debug_metadata() -> None:
    knowledge_base_id = uuid4()
    service = FakeHybridRetrievalService()
    service.results = (
        HybridRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=2,
            text="shared result",
            start_offset=100,
            end_offset=113,
            rrf_score=0.0325,
            vector_rank=1,
            keyword_rank=2,
            cosine_similarity=0.91,
            keyword_score=0.72,
        ),
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/hybrid",
        json={
            "query": "  authentication architecture  ",
            "top_k": 10,
            "candidate_k": 50,
            "rrf_k": 60,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hybrid"
    assert body["query"] == "authentication architecture"
    assert body["top_k"] == 10
    assert body["candidate_k"] == 50
    assert body["rrf_k"] == 60
    assert body["matches"][0]["rank"] == 1
    assert body["matches"][0]["vector_rank"] == 1
    assert body["matches"][0]["keyword_rank"] == 2
    assert body["matches"][0]["cosine_similarity"] == 0.91
    assert body["matches"][0]["keyword_score"] == 0.72
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "  authentication architecture  ",
        "limit": 10,
        "candidate_limit": 50,
        "rrf_k": 60,
    }


def test_hybrid_retrieval_rejects_candidate_k_below_top_k() -> None:
    client = _client(FakeHybridRetrievalService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/hybrid",
        json={
            "query": "query",
            "top_k": 20,
            "candidate_k": 10,
            "rrf_k": 60,
        },
    )

    assert response.status_code == 422


def test_hybrid_retrieval_hides_fusion_integrity_errors() -> None:
    service = FakeHybridRetrievalService()
    service.error = HybridRetrievalResultError("internal metadata mismatch")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/hybrid",
        json={"query": "query"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval service temporarily unavailable"
    }
    assert "internal metadata mismatch" not in response.text
