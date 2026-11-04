"""Per-stage metadata in retrieval responses and historical endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.retrieval.dependencies import (
    get_traced_hybrid_retrieval_service,
    get_traced_keyword_retrieval_service,
    get_traced_vector_retrieval_service,
)
from spurel.retrieval.traced import TracedRetrievalResult
from spurel.security import require_api_token


class FakeTracedRetriever:
    def __init__(self, stage_timings_ms):
        self.stage_timings_ms = stage_timings_ms

    async def search(self, **kwargs):
        return TracedRetrievalResult(
            trace_id=uuid4(), duration_ms=8.0, matches=(),
            stage_timings_ms=self.stage_timings_ms,
        )


def test_all_retrieval_modes_expose_actual_stages_without_changing_requests() -> None:
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    scopes = {
        "vector": (get_traced_vector_retrieval_service, {"query_embedding": 3.0}),
        "keyword": (get_traced_keyword_retrieval_service, {"keyword_search": 5.0}),
        "hybrid": (get_traced_hybrid_retrieval_service, {"rrf_fusion": 0.5}),
    }
    for dependency, values in scopes.values():
        app.dependency_overrides[dependency] = lambda values=values: FakeTracedRetriever(values)

    client = TestClient(app)
    for mode, (_, expected) in scopes.items():
        response = client.post(
            f"/knowledge-bases/{uuid4()}/retrieval/{mode}",
            json={"query": "test"},
        )
        assert response.status_code == 200
        assert response.json()["stage_timings_ms"] == expected
        assert response.json()["duration_ms"] == 8.0
    app.dependency_overrides.clear()
