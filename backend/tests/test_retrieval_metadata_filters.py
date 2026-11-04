"""SP-19 metadata filter contracts and SQL predicate unit tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from spurel.documents.domain import DocumentMediaType
from spurel.documents.persistence import DocumentRecord
from spurel.main import create_app
from spurel.retrieval.dependencies import (
    get_traced_hybrid_retrieval_service,
    get_traced_keyword_retrieval_service,
    get_traced_vector_retrieval_service,
)
from spurel.retrieval.metadata_filters import (
    RetrievalMetadataFilterError,
    RetrievalMetadataFilters,
)
from spurel.retrieval.schemas import RetrievalMetadataFiltersRequest
from spurel.retrieval.sql_metadata_filters import apply_document_metadata_filters
from spurel.retrieval.traced import TracedRetrievalResult
from spurel.security import require_api_token


def test_filter_snapshot_is_roundtrippable_and_UTC_normalized() -> None:
    document_id = uuid4()
    f = RetrievalMetadataFilters(
        document_ids=(document_id,),
        media_types=(DocumentMediaType.MARKDOWN,),
        filename_contains="100%_manual\\",
        created_after=datetime(2026, 1, 1, tzinfo=UTC),
        created_before=datetime(2026, 12, 31, tzinfo=UTC),
    )
    snapshot = f.to_snapshot()
    assert snapshot["document_ids"] == [str(document_id)]
    assert snapshot["media_types"] == ["text/markdown"]
    assert RetrievalMetadataFilters.from_snapshot(snapshot) == f


@pytest.mark.parametrize("options", [
    {},
    {"filename_contains": "  "},
    {"filename_contains": "x" * 101},
    {"document_ids": (uuid4(),) * 2},
    {"media_types": (DocumentMediaType.PDF,) * 2},
    {"created_after": datetime(2026, 1, 1)},
    {"created_after": datetime(2026, 2, 1, tzinfo=UTC),
     "created_before": datetime(2026, 1, 1, tzinfo=UTC)},
])
def test_filter_rejects_invalid_criteria(options) -> None:
    with pytest.raises(RetrievalMetadataFilterError):
        RetrievalMetadataFilters(**options)


def test_metadata_filter_request_rejects_unknown_keys_and_invalid_values() -> None:
    inputs = [
        {},
        {"unknown": "unsafe"},
        {"filename_contains": "\n"},
        {"document_ids": [str(uuid4())] * 2},
        {"document_ids": ["../../../etc/passwd"]},
        {"media_types": ["text/html"]},
        {"created_after": "2026-01-01T00:00:00"},
        {"created_before": "2026-02-01T00:00:00Z",
         "created_after": "2026-03-01T00:00:00Z"},
    ]
    for candidate in inputs:
        with pytest.raises(ValueError):
            RetrievalMetadataFiltersRequest.model_validate(candidate)


def test_sql_predicates_are_applied_before_limit_and_escape_like_operators() -> None:
    doc_id = uuid4()
    date = datetime.now(UTC) - timedelta(days=2)
    filters = RetrievalMetadataFilters(
        document_ids=(doc_id,),
        media_types=(DocumentMediaType.PDF,),
        filename_contains="100%_report\\",
        created_after=date,
    )
    original = select(DocumentRecord.id).order_by(DocumentRecord.id).limit(10)
    statement = apply_document_metadata_filters(original, filters)
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "documents.id IN" in sql
    assert "documents.media_type IN" in sql
    assert "documents.filename ILIKE" in sql
    assert "ESCAPE" in sql
    assert "documents.created_at >=" in sql
    assert "LIMIT" in sql
    assert any(value == "%100\\%\\_report\\\\%" for value in compiled.params.values())
    assert any(value == doc_id for value in compiled.params.values())
    assert any(value == date for value in compiled.params.values())
    assert apply_document_metadata_filters(original, None) is original


class _FakeTracedRetriever:
    def __init__(self):
        self.calls = []
        self.trace_id = uuid4()

    async def search(self, *, knowledge_base_id, query, limit, **kwargs):
        self.calls.append({
            "kb": knowledge_base_id, "query": query, "limit": limit,
            "filters": kwargs.get("filters"), "candidate_limit": kwargs.get("candidate_limit"),
            "rrf_k": kwargs.get("rrf_k"),
        })
        return TracedRetrievalResult(trace_id=self.trace_id, duration_ms=1.0, matches=())


def _api_client(fake):
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    app.dependency_overrides[get_traced_vector_retrieval_service] = lambda: fake
    app.dependency_overrides[get_traced_keyword_retrieval_service] = lambda: fake
    app.dependency_overrides[get_traced_hybrid_retrieval_service] = lambda: fake
    return TestClient(app)


@pytest.mark.parametrize("mode", ["keyword", "vector", "hybrid"])
def test_all_retrieval_routes_accept_identical_filters_without_changing_defaults(mode) -> None:
    fake = _FakeTracedRetriever()
    client = _api_client(fake)
    kb = uuid4()
    document_id = uuid4()
    explicit = {
        "query": "refund policy", "top_k": 5,
        "filters": {"document_ids": [str(document_id)], "media_types": ["text/plain"]},
    }
    if mode == "hybrid":
        explicit.update({"candidate_k": 10, "rrf_k": 60})
    res = client.post(f"/knowledge-bases/{kb}/retrieval/{mode}", json=explicit)
    assert res.status_code == 200, res.text
    assert res.json()["filters"]["document_ids"] == [str(document_id)]
    assert fake.calls[-1]["filters"] == RetrievalMetadataFilters(
        document_ids=(document_id,), media_types=(DocumentMediaType.TEXT,)
    )
    legacy = {key: value for key, value in explicit.items() if key != "filters"}
    assert client.post(f"/knowledge-bases/{kb}/retrieval/{mode}", json=legacy).status_code == 200
    assert fake.calls[-1]["filters"] is None


@pytest.mark.parametrize("mode", ["keyword", "vector", "hybrid"])
def test_all_retrieval_routes_reject_invalid_metadata_before_execution(mode) -> None:
    fake = _FakeTracedRetriever()
    client = _api_client(fake)
    payload = {"query": "refund", "top_k": 5}
    if mode == "hybrid":
        payload.update(candidate_k=10, rrf_k=60)
    for invalid in (
        {},
        {"media_types": ["text/html"]},
        {"document_ids": [str(uuid4())] * 2},
        {"filename_contains": " "},
        {"created_after": "2026-04-01T00:00:00"},
        {"filename_contains": "policy", "unexpected": True},
    ):
        result = client.post(
            f"/knowledge-bases/{uuid4()}/retrieval/{mode}",
            json={**payload, "filters": invalid},
        )
        assert result.status_code == 422
    assert fake.calls == []
