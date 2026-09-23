from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.retrieval.dependencies import get_vector_retrieval_service
from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.ports import VectorRetrievalRepositoryError
from spurel.main import create_app


class FakeVectorRetrievalService:
    def __init__(self) -> None:
        self.results: Sequence[VectorRetrievalMatch] = ()
        self.fail = False
        self.last_call: dict[str, object] | None = None

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
        }
        if self.fail:
            raise VectorRetrievalRepositoryError(
                "database/provider secret details"
            )
        return self.results


def _client(service: FakeVectorRetrievalService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_vector_retrieval_service] = lambda: service
    return TestClient(application)


def test_vector_retrieval_returns_ranked_public_matches() -> None:
    service = FakeVectorRetrievalService()
    knowledge_base_id = uuid4()
    service.results = (
        VectorRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=3,
            text="first match",
            start_offset=100,
            end_offset=111,
            cosine_similarity=0.94,
        ),
        VectorRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=7,
            text="second match",
            start_offset=200,
            end_offset=212,
            cosine_similarity=0.81,
        ),
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/vector",
        json={"query": "  architecture  ", "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "vector"
    assert body["query"] == "architecture"
    assert body["top_k"] == 5
    assert [match["rank"] for match in body["matches"]] == [1, 2]
    assert [match["cosine_similarity"] for match in body["matches"]] == [
        0.94,
        0.81,
    ]
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "  architecture  ",
        "limit": 5,
    }


def test_vector_retrieval_rejects_excessive_top_k() -> None:
    client = _client(FakeVectorRetrievalService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/vector",
        json={"query": "query", "top_k": 101},
    )

    assert response.status_code == 422


def test_vector_retrieval_does_not_leak_infrastructure_errors() -> None:
    service = FakeVectorRetrievalService()
    service.fail = True
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/vector",
        json={"query": "query", "top_k": 10},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval service temporarily unavailable"
    }
    assert "secret details" not in response.text
