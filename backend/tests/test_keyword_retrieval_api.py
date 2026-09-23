from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import get_traced_keyword_retrieval_service
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError
from spurel.retrieval.traced import TracedRetrievalResult


class FakeKeywordRetrievalService:
    def __init__(self) -> None:
        self.results: Sequence[KeywordRetrievalMatch] = ()
        self.fail = False
        self.last_call: dict[str, object] | None = None
        self.trace_id = uuid4()
        self.duration_ms = 8.25

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> TracedRetrievalResult[KeywordRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
        }
        if self.fail:
            raise KeywordRetrievalRepositoryError("database secret details")
        return TracedRetrievalResult(
            trace_id=self.trace_id,
            duration_ms=self.duration_ms,
            matches=tuple(self.results),
        )


def _client(service: FakeKeywordRetrievalService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_traced_keyword_retrieval_service] = lambda: service
    return TestClient(application)


def test_keyword_retrieval_returns_ranked_public_matches() -> None:
    knowledge_base_id = uuid4()
    service = FakeKeywordRetrievalService()
    service.results = (
        KeywordRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=1,
            text="authentication architecture",
            start_offset=100,
            end_offset=127,
            keyword_score=0.82,
        ),
        KeywordRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=4,
            text="authentication details",
            start_offset=300,
            end_offset=322,
            keyword_score=0.61,
        ),
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/keyword",
        json={"query": "  authentication  ", "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "keyword"
    assert body["query"] == "authentication"
    assert body["top_k"] == 5
    assert body["trace_id"] == str(service.trace_id)
    assert body["duration_ms"] == 8.25
    assert [item["rank"] for item in body["matches"]] == [1, 2]
    assert [item["keyword_score"] for item in body["matches"]] == [
        0.82,
        0.61,
    ]
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "  authentication  ",
        "limit": 5,
    }


def test_keyword_retrieval_rejects_excessive_top_k() -> None:
    client = _client(FakeKeywordRetrievalService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/keyword",
        json={"query": "query", "top_k": 101},
    )

    assert response.status_code == 422


def test_keyword_retrieval_hides_repository_errors() -> None:
    service = FakeKeywordRetrievalService()
    service.fail = True
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/keyword",
        json={"query": "query", "top_k": 10},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval service temporarily unavailable"
    }
    assert "secret details" not in response.text
