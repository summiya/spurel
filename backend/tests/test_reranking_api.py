"""SP-21: reranking is opt-in, typed, and preserves the existing hybrid API."""

from uuid import uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import get_traced_hybrid_retrieval_service
from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.reranking import RerankerUnavailableError
from spurel.retrieval.traced import TracedRetrievalResult
from spurel.security import require_api_token


class FakeRerankedService:
    def __init__(self) -> None:
        self.requests: list[bool] = []
        self.error = False

    async def search(
        self, *, knowledge_base_id, query, limit, candidate_limit, rrf_k, rerank=False
    ):
        self.requests.append(rerank)
        if self.error and rerank:
            raise RerankerUnavailableError("secret upstream URL")
        match = HybridRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=0,
            text="real persisted chunk",
            start_offset=0,
            end_offset=20,
            rrf_score=0.032,
            vector_rank=1,
            keyword_rank=2,
            cosine_similarity=0.95,
            keyword_score=0.5,
            candidate_rank=2 if rerank else None,
            rerank_rank=1 if rerank else None,
            rerank_score=0.92 if rerank else None,
        )
        return TracedRetrievalResult(
            trace_id=uuid4(),
            duration_ms=10.0,
            matches=(match,),
            reranker_model="local-test-cross-encoder" if rerank else None,
        )


def _client(service):
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    app.dependency_overrides[get_traced_hybrid_retrieval_service] = lambda: service
    return TestClient(app)


def test_hybrid_reranking_is_explicit_and_returns_candidate_rank_metadata() -> None:
    service = FakeRerankedService()
    client = _client(service)
    url = f"/knowledge-bases/{uuid4()}/retrieval/hybrid"
    ordinary = client.post(url, json={"query": "q"})
    assert ordinary.status_code == 200
    assert ordinary.json()["rerank"] is False
    assert ordinary.json()["reranker_model"] is None
    assert ordinary.json()["matches"][0]["rerank_score"] is None

    reranked = client.post(url, json={"query": "q", "rerank": True})
    assert reranked.status_code == 200
    assert reranked.json()["rerank"] is True
    assert reranked.json()["reranker_model"] == "local-test-cross-encoder"
    assert reranked.json()["matches"][0]["candidate_rank"] == 2
    assert reranked.json()["matches"][0]["rerank_rank"] == 1
    assert reranked.json()["matches"][0]["rerank_score"] == 0.92
    assert service.requests == [False, True]


def test_hybrid_rejects_nonboolean_rerank_and_masks_upstream_errors() -> None:
    service = FakeRerankedService()
    service.error = True
    client = _client(service)
    url = f"/knowledge-bases/{uuid4()}/retrieval/hybrid"
    assert client.post(url, json={"query": "q", "rerank": "yes"}).status_code == 422
    response = client.post(url, json={"query": "q", "rerank": True})
    assert response.status_code == 503
    assert "secret upstream" not in response.text
