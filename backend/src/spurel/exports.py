"""Read-only, bounded JSON and CSV exports of persisted experiment snapshots.

The exported configuration and metrics come from the saved snapshot, not
current provider settings. JSON retains nulls and numeric types; CSV contains
one row per saved result/case and repeats its experiment metadata.
"""

import csv
import json
from io import StringIO
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ExportKind = Literal["retrieval_trace", "evaluation_run"]
ExportFormat = Literal["json", "csv"]
MAX_EXPORT_BYTES = 5 * 1024 * 1024

_TRACE_CONFIGURATION = (
    "mode",
    "query",
    "top_k",
    "candidate_k",
    "rrf_k",
    "embedding_provider",
    "embedding_model",
    "embedding_dimensions",
    "filters",
    "reranker_model",
)
_RUN_CONFIGURATION = (
    "mode",
    "top_k",
    "candidate_k",
    "rrf_k",
    "embedding_provider",
    "embedding_model",
    "embedding_dimensions",
)
_SOURCE_FIELDS = ("id", "run_id", "knowledge_base_id", "dataset_id", "created_at")


class ExportSizeError(ValueError):
    """A persisted snapshot exceeds the bounded single-record export limit."""


class ArtifactExportResponse(BaseModel):
    """Fixed-name download returned through the protected API boundary."""

    filename: str = Field(min_length=1, max_length=120)
    media_type: Literal["application/json", "text/csv"]
    content: str


def _csv_value(value: Any) -> str | int | float:
    """Protect string cells against spreadsheet formula execution.

    Numeric metrics remain typed numeric. Queries, excerpts, model names and
    any nested JSON strings are untrusted source text, not spreadsheet code.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return value
    else:
        value = str(value)

    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_snapshot(
    *,
    kind: ExportKind,
    snapshot: BaseModel,
    record_id: UUID,
    format: ExportFormat,
) -> ArtifactExportResponse:
    """Serialize only an already persisted, scope-checked API response."""
    data = snapshot.model_dump(mode="json")
    if kind == "retrieval_trace":
        expected = data["id"]
        records_key = "results"
        config_keys = _TRACE_CONFIGURATION
        filename_prefix = "spurel-trace"
        row_prefix = "result"
    else:
        expected = data["run_id"]
        records_key = "cases"
        config_keys = _RUN_CONFIGURATION
        filename_prefix = "spurel-evaluation-run"
        row_prefix = "case"

    if expected != str(record_id):
        raise ValueError("export snapshot identity does not match the requested record")

    records = data[records_key]
    configuration = {key: data[key] for key in config_keys}
    source = {key: data[key] for key in _SOURCE_FIELDS if key in data}
    excluded = set(config_keys) | set(source) | {records_key}
    metrics = {key: value for key, value in data.items() if key not in excluded}
    if kind == "retrieval_trace":
        metrics["result_count"] = len(records)

    envelope = {
        "schema_version": 1,
        "artifact_type": kind,
        "source": source,
        "configuration": configuration,
        "metrics": metrics,
        records_key: records,
    }

    if format == "json":
        content = json.dumps(envelope, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        media_type = "application/json"
    elif format == "csv":
        metadata = {
            "schema_version": 1,
            "artifact_type": kind,
            **source,
            "record_count": len(records),
            **{f"config_{key}": value for key, value in configuration.items()},
            **{f"metric_{key}": value for key, value in metrics.items()},
        }
        row_names = list(records[0]) if records else []
        fieldnames = [*metadata, *(f"{row_prefix}_{key}" for key in row_names)]
        buffer = StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        # A saved empty retrieval is still exported as one metadata row.
        for record in records or [{}]:
            row = {
                **metadata,
                **{f"{row_prefix}_{key}": value for key, value in record.items()},
            }
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
        content = buffer.getvalue()
        media_type = "text/csv"
    else:
        raise ValueError("unsupported export format")

    if len(content.encode("utf-8")) > MAX_EXPORT_BYTES:
        raise ExportSizeError("saved snapshot exceeds single-export size limit")

    return ArtifactExportResponse(
        filename=f"{filename_prefix}-{record_id}.{format}",
        media_type=media_type,
        content=content,
    )
