from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import get_retrieval_trace_service
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.trace_service import RetrievalTraceNotFoundError
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
    RetrievalTraceSummary,
)
from spurel.security import require_api_token


class FakeRetrievalTraceService:
    def __init__(self) -> None:
        self.summaries: tuple[RetrievalTraceSummary, ...] = ()
        self.trace: RetrievalTrace | None = None
        self.list_error: Exception | None = None
        self.get_error: Exception | None = None

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ):
        if self.list_error is not None:
            raise self.list_error
        return self.summaries

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace:
        if self.get_error is not None:
            raise self.get_error
        if self.trace is None:
            raise RetrievalTraceNotFoundError("missing")
        return self.trace


def _client(service: FakeRetrievalTraceService) -> TestClient:
    application = create_app()
    application.dependency_overrides[require_api_token] = lambda: None
    application.dependency_overrides[get_retrieval_trace_service] = lambda: service
    return TestClient(application)


def test_trace_history_returns_bounded_summaries() -> None:
    knowledge_base_id = uuid4()
    service = FakeRetrievalTraceService()
    service.summaries = (
        RetrievalTraceSummary(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.HYBRID,
            query="authentication architecture",
            top_k=10,
            candidate_k=50,
            rrf_k=60,
            duration_ms=12.5,
            stage_timings_ms={"query_embedding": 3.3, "vector_search": 4.1},
            embedding_provider="openai",
            embedding_model="text-embedding-example",
            embedding_dimensions=1536,
            result_count=10,
            created_at=datetime.now(UTC),
        ),
    )
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/traces",
        params={"limit": 25, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["mode"] == "hybrid"
    assert body["items"][0]["result_count"] == 10
    assert body["items"][0]["stage_timings_ms"] == {
        "query_embedding": 3.3,
        "vector_search": 4.1,
    }
    assert "results" not in body["items"][0]


def test_trace_history_bounds_page_size() -> None:
    client = _client(FakeRetrievalTraceService())

    response = client.get(
        f"/knowledge-bases/{uuid4()}/retrieval/traces",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_trace_detail_returns_complete_ranked_snapshot() -> None:
    knowledge_base_id = uuid4()
    trace_id = uuid4()
    service = FakeRetrievalTraceService()
    service.trace = RetrievalTrace(
        id=trace_id,
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.VECTOR,
        query="architecture",
        top_k=5,
        candidate_k=None,
        rrf_k=None,
        duration_ms=9.75,
        stage_timings_ms={"query_embedding": 2.4, "vector_search": 5.1},
        embedding_provider="openai",
        embedding_model="text-embedding-example",
        embedding_dimensions=1536,
        results=(
            RetrievalTraceResult(
                rank=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                chunk_index=2,
                text="snapshot text",
                start_offset=100,
                end_offset=113,
                cosine_similarity=0.93,
            ),
        ),
        created_at=datetime.now(UTC),
    )
    client = _client(service)

    response = client.get(f"/knowledge-bases/{knowledge_base_id}/retrieval/traces/{trace_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(trace_id)
    assert body["knowledge_base_id"] == str(knowledge_base_id)
    assert body["mode"] == "vector"
    assert body["duration_ms"] == 9.75
    assert body["stage_timings_ms"] == {"query_embedding": 2.4, "vector_search": 5.1}
    assert body["results"][0]["rank"] == 1
    assert body["results"][0]["text"] == "snapshot text"
    assert body["results"][0]["cosine_similarity"] == 0.93


def test_trace_detail_returns_scoped_not_found() -> None:
    service = FakeRetrievalTraceService()
    service.get_error = RetrievalTraceNotFoundError("internal existence detail")
    client = _client(service)

    response = client.get(f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "retrieval trace was not found"}
    assert "internal existence detail" not in response.text


def test_trace_history_hides_persistence_errors() -> None:
    service = FakeRetrievalTraceService()
    service.list_error = RetrievalTracePersistenceError("database secret detail")
    client = _client(service)

    response = client.get(f"/knowledge-bases/{uuid4()}/retrieval/traces")

    assert response.status_code == 503
    assert response.json() == {"detail": "retrieval trace history temporarily unavailable"}
    assert "database secret detail" not in response.text


def test_trace_export_json_and_csv_have_exact_scope_and_no_rerun() -> None:
    import csv
    import json
    from io import StringIO

    knowledge_base_id = uuid4()
    service = FakeRetrievalTraceService()
    service.trace = RetrievalTrace(
        id=uuid4(),
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.KEYWORD,
        query="  =SUM(3,4)",
        top_k=5,
        candidate_k=None,
        rrf_k=None,
        duration_ms=12.0,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        results=(
            RetrievalTraceResult(
                rank=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                chunk_index=0,
                text="-HYPERLINK('bad')",
                start_offset=0,
                end_offset=17,
                keyword_score=0.4,
            ),
        ),
        created_at=datetime.now(UTC),
    )
    root = f"/knowledge-bases/{knowledge_base_id}/retrieval/traces/{service.trace.id}/export"
    client = _client(service)
    exported = client.get(root, params={"format": "json"})
    assert exported.status_code == 200
    data = json.loads(exported.json()["content"])
    assert data["source"]["id"] == str(service.trace.id)
    assert data["configuration"]["mode"] == "keyword"
    assert data["metrics"]["duration_ms"] == 12.0
    assert data["results"][0]["keyword_score"] == 0.4

    csv_result = client.get(root, params={"format": "csv"})
    assert csv_result.status_code == 200
    row = list(csv.DictReader(StringIO(csv_result.json()["content"])))[0]
    assert row["config_query"].startswith("'  =SUM")
    assert row["result_text"].startswith("'-HYPERLINK")
    assert row["result_keyword_score"] == "0.4"

    assert client.get(root, params={"format": "xml"}).status_code == 422
    assert client.get(root.replace(str(knowledge_base_id), str(uuid4()))).status_code == 404
    assert client.get(root.replace(str(service.trace.id), str(uuid4()))).status_code == 404


def test_trace_export_preserves_not_found_and_generic_database_errors() -> None:
    service = FakeRetrievalTraceService()
    client = _client(service)
    url = f"/knowledge-bases/{uuid4()}/retrieval/traces/{uuid4()}/export"
    missing = client.get(url)
    assert missing.status_code == 404
    service.get_error = RetrievalTracePersistenceError("secret db endpoint")
    failed = client.get(url)
    assert failed.status_code == 503
    assert "secret db endpoint" not in failed.text
