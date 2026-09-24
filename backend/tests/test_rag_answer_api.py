from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.generation.ports import TextGenerationProviderError
from spurel.main import create_app
from spurel.rag.dependencies import get_rag_answer_service
from spurel.rag.service import RAGAnswer


class FakeRAGAnswerService:
    def __init__(self) -> None:
        self.result = RAGAnswer(
            trace_id=uuid4(),
            answer="Grounded answer.",
            retrieved_chunk_count=2,
            generation_provider="fake",
            generation_model="fake-model",
        )
        self.error: Exception | None = None
        self.last_call: dict[str, object] | None = None

    async def answer(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        candidate_k: int,
        rrf_k: int,
    ) -> RAGAnswer:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "rrf_k": rrf_k,
        }
        if self.error is not None:
            raise self.error
        return self.result


def _client(service: FakeRAGAnswerService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_rag_answer_service] = lambda: service
    return TestClient(application)


def test_rag_answer_returns_grounded_result_metadata() -> None:
    knowledge_base_id = uuid4()
    service = FakeRAGAnswerService()
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/rag/answer",
        json={
            "query": "  How does authentication work?  ",
            "top_k": 8,
            "candidate_k": 50,
            "rrf_k": 60,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "trace_id": str(service.result.trace_id),
        "answer": "Grounded answer.",
        "retrieved_chunk_count": 2,
        "generation_provider": "fake",
        "generation_model": "fake-model",
    }
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "  How does authentication work?  ",
        "top_k": 8,
        "candidate_k": 50,
        "rrf_k": 60,
    }


def test_rag_answer_rejects_candidate_pool_below_top_k() -> None:
    client = _client(FakeRAGAnswerService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/rag/answer",
        json={
            "query": "question",
            "top_k": 12,
            "candidate_k": 10,
        },
    )

    assert response.status_code == 422


def test_rag_answer_bounds_context_top_k() -> None:
    client = _client(FakeRAGAnswerService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/rag/answer",
        json={
            "query": "question",
            "top_k": 21,
        },
    )

    assert response.status_code == 422


def test_rag_answer_hides_generation_provider_errors() -> None:
    service = FakeRAGAnswerService()
    service.error = TextGenerationProviderError("provider secret detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/rag/answer",
        json={"query": "question"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "RAG service temporarily unavailable"
    }
    assert "provider secret detail" not in response.text
