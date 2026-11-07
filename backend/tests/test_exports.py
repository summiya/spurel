"""SP-26 immutable snapshot export shape and untrusted CSV cell safety."""

import csv
import json
from io import StringIO
from uuid import uuid4

import pytest

from spurel.exports import ExportSizeError, export_snapshot
from spurel.retrieval.schemas import (
    RetrievalTraceDetailResponse,
    RetrievalTraceResultResponse,
)


def _trace(*, query: str, text: str, empty: bool = False) -> RetrievalTraceDetailResponse:
    return RetrievalTraceDetailResponse(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        mode="keyword",
        query=query,
        top_k=5,
        candidate_k=None,
        rrf_k=None,
        duration_ms=9.75,
        stage_timings_ms={"keyword_search": 7.4},
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        created_at="2026-11-03T18:00:00Z",
        filters=None,
        reranker_model=None,
        results=[] if empty else [
            RetrievalTraceResultResponse(
                rank=1,
                chunk_id=uuid4(),
                document_id=uuid4(),
                chunk_index=0,
                text=text,
                start_offset=0,
                end_offset=len(text),
                cosine_similarity=None,
                keyword_score=0.123,
                rrf_score=None,
                vector_rank=None,
                keyword_rank=1,
            ),
        ],
    )


def test_json_export_keeps_exact_saved_configuration_and_numeric_scores() -> None:
    trace = _trace(query="A policy question", text="Saved Unicode evidence — ✓")
    result = export_snapshot(
        kind="retrieval_trace", snapshot=trace, record_id=trace.id, format="json"
    )
    payload = json.loads(result.content)
    assert result.filename == f"spurel-trace-{trace.id}.json"
    assert result.media_type == "application/json"
    assert payload["schema_version"] == 1
    assert payload["artifact_type"] == "retrieval_trace"
    assert payload["source"]["id"] == str(trace.id)
    assert payload["source"]["knowledge_base_id"] == str(trace.knowledge_base_id)
    assert payload["configuration"]["query"] == "A policy question"
    assert payload["configuration"]["filters"] is None
    assert payload["metrics"]["duration_ms"] == 9.75
    assert payload["metrics"]["stage_timings_ms"] == {"keyword_search": 7.4}
    assert payload["metrics"]["result_count"] == 1
    assert payload["results"][0]["keyword_score"] == 0.123
    assert payload["results"][0]["cosine_similarity"] is None
    assert payload["results"][0]["text"] == "Saved Unicode evidence — ✓"


def test_csv_quotes_multiline_evidence_and_neutralizes_spreadsheet_formulas() -> None:
    trace = _trace(query=" \t=HYPERLINK(\"evil\")", text="+SUM(1,2)\nprivate ✓")
    csv_file = export_snapshot(
        kind="retrieval_trace", snapshot=trace, record_id=trace.id, format="csv"
    )
    rows = list(csv.DictReader(StringIO(csv_file.content, newline="")))
    assert csv_file.media_type == "text/csv"
    assert csv_file.filename == f"spurel-trace-{trace.id}.csv"
    assert len(rows) == 1
    row = rows[0]
    assert row["config_query"].startswith("' \t=HYPERLINK")
    assert row["result_text"] == "'+SUM(1,2)\nprivate ✓"
    assert row["metric_duration_ms"] == "9.75"
    assert row["result_keyword_score"] == "0.123"
    assert row["metric_stage_timings_ms"] == '{"keyword_search":7.4}'


def test_empty_traces_export_configuration_without_inventing_results() -> None:
    trace = _trace(query="Empty answer", text="unused", empty=True)
    json_file = export_snapshot(
        kind="retrieval_trace", snapshot=trace, record_id=trace.id, format="json"
    )
    body = json.loads(json_file.content)
    assert body["results"] == []
    assert body["metrics"]["result_count"] == 0

    csv_file = export_snapshot(
        kind="retrieval_trace", snapshot=trace, record_id=trace.id, format="csv"
    )
    row = list(csv.DictReader(StringIO(csv_file.content)))[0]
    assert row["record_count"] == "0"
    assert row["config_query"] == "Empty answer"


def test_export_identity_and_payload_size_fail_closed(monkeypatch) -> None:
    trace = _trace(query="bounded", text="persisted evidence")
    with pytest.raises(ValueError, match="identity"):
        export_snapshot(
            kind="retrieval_trace", snapshot=trace, record_id=uuid4(), format="json"
        )
    monkeypatch.setattr("spurel.exports.MAX_EXPORT_BYTES", 80)
    with pytest.raises(ExportSizeError):
        export_snapshot(
            kind="retrieval_trace", snapshot=trace, record_id=trace.id, format="json"
        )
