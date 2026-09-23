from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import (
    get_retrieval_trace_comparison_service,
)
from spurel.retrieval.trace_comparison import (
    RetrievalTraceComparison,
    RetrievalTraceComparisonIntegrityError,
    RetrievalTraceComparisonResult,
    RetrievalTraceComparisonSide,
)
from spurel.retrieval.trace_service import RetrievalTraceNotFoundError
from spurel.retrieval.tracing import RetrievalTraceMode


class FakeTraceComparisonService:
    def __init__(self) -> None:
        self.result: RetrievalTraceComparison | None = None
        self.error: Exception | None = None
        self.last_call: dict[str, UUID] | None = None

    async def compare(
        self,
        *,
        knowledge_base_id: UUID,
        first_trace_id: UUID,
        second_trace_id: UUID,
    ) -> RetrievalTraceComparison:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "first_trace_id": first_trace_id,
            "second_trace_id": second_trace_id,
        }
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeTraceComparisonService) -> TestClient:
    application = create_app()
    application.dependency_overrides[
        get_retrieval_trace_comparison_service
    ] = lambda: service
    return TestClient(application)


def test_trace_comparison_returns_descriptive_side_by_side_metrics() -> None:
    knowledge_base_id = uuid4()
    first_trace_id = uuid4()
    second_trace_id = uuid4()
    chunk_id = uuid4()
    document_id = uuid4()

    service = FakeTraceComparisonService()
    service.result = RetrievalTraceComparison(
        first=RetrievalTraceComparisonSide(
            trace_id=first_trace_id,
            mode=RetrievalTraceMode.VECTOR,
            query="authentication",
            top_k=10,
            candidate_k=None,
            rrf_k=None,
            duration_ms=12.0,
            embedding_provider="openai",
            embedding_model="model-a",
            embedding_dimensions=1536,
            result_count=10,
        ),
        second=RetrievalTraceComparisonSide(
            trace_id=second_trace_id,
            mode=RetrievalTraceMode.HYBRID,
            query="authentication",
            top_k=10,
            candidate_k=50,
            rrf_k=60,
            duration_ms=8.0,
            embedding_provider="openai",
            embedding_model="model-a",
            embedding_dimensions=1536,
            result_count=10,
        ),
        same_query=True,
        overlap_count=7,
        union_count=13,
        overlap_ratio=7 / 13,
        first_only_count=3,
        second_only_count=3,
        duration_delta_ms=-4.0,
        results=(
            RetrievalTraceComparisonResult(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=2,
                text="shared chunk",
                start_offset=100,
                end_offset=112,
                first_rank=4,
                second_rank=2,
                rank_delta=-2,
                first_cosine_similarity=0.88,
                second_cosine_similarity=0.9,
                first_keyword_score=None,
                second_keyword_score=0.7,
                first_rrf_score=None,
                second_rrf_score=0.03,
            ),
        ),
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/retrieval/trace-comparisons",
        json={
            "first_trace_id": str(first_trace_id),
            "second_trace_id": str(second_trace_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first"]["mode"] == "vector"
    assert body["second"]["mode"] == "hybrid"
    assert body["same_query"] is True
    assert body["overlap_count"] == 7
    assert body["union_count"] == 13
    assert body["duration_delta_ms"] == -4.0
    assert body["results"][0]["first_rank"] == 4
    assert body["results"][0]["second_rank"] == 2
    assert body["results"][0]["rank_delta"] == -2
    assert body["results"][0]["second_rrf_score"] == 0.03
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "first_trace_id": first_trace_id,
        "second_trace_id": second_trace_id,
    }


def test_trace_comparison_rejects_same_trace_id_at_http_boundary() -> None:
    trace_id = uuid4()
    client = _client(FakeTraceComparisonService())

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/trace-comparisons",
        json={
            "first_trace_id": str(trace_id),
            "second_trace_id": str(trace_id),
        },
    )

    assert response.status_code == 422


def test_trace_comparison_returns_scoped_not_found() -> None:
    service = FakeTraceComparisonService()
    service.error = RetrievalTraceNotFoundError("cross-knowledge-base detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/trace-comparisons",
        json={
            "first_trace_id": str(uuid4()),
            "second_trace_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "retrieval trace was not found"}
    assert "cross-knowledge-base detail" not in response.text


def test_trace_comparison_hides_snapshot_integrity_errors() -> None:
    service = FakeTraceComparisonService()
    service.error = RetrievalTraceComparisonIntegrityError(
        "historical snapshot internals"
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/retrieval/trace-comparisons",
        json={
            "first_trace_id": str(uuid4()),
            "second_trace_id": str(uuid4()),
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval trace comparison temporarily unavailable"
    }
    assert "historical snapshot internals" not in response.text
