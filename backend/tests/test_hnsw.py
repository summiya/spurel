"""SP-20 HNSW design contracts: explicit build, recall math and safe scoping."""

from io import StringIO
from uuid import uuid4

import pytest

from spurel.retrieval.hnsw import (
    HnswBenchmarkError,
    HnswBenchmarkOptions,
    HnswConfigurationError,
    HnswIndexOptions,
    _percentile_95,
    _plan_uses_index,
    _retrieval_query,
    _summarize,
    _vector_literal,
)
from spurel.retrieval.hnsw_cli import run_hnsw_cli


def _benchmark_options(**updates) -> HnswBenchmarkOptions:
    values = {
        "knowledge_base_id": uuid4(),
        "provider": "openai",
        "model": "text-embedding-3-small",
        "dimensions": 1536,
        "top_k": 10,
        "samples": 4,
        "ef_search": 100,
    }
    values.update(updates)
    return HnswBenchmarkOptions(**values)


def test_dimension_specific_concurrent_ddl_is_opt_in_and_safe() -> None:
    opts = HnswIndexOptions(dimensions=1536)
    assert opts.index_name == "ix_spurel_hnsw_cosine_d1536"
    assert opts.build_statement == (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_spurel_hnsw_cosine_d1536 "
        "ON chunk_embeddings USING hnsw "
        "((embedding::vector(1536)) vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64) "
        "WHERE dimensions = 1536"
    )
    assert "DROP" not in opts.build_statement
    assert "IF NOT EXISTS" in opts.build_statement


@pytest.mark.parametrize("bad_dimensions", [0, 2001, -1, True, 1.5, "1536"])
def test_reject_unindexable_dimensions(bad_dimensions: object) -> None:
    with pytest.raises(HnswConfigurationError):
        HnswIndexOptions(dimensions=bad_dimensions)  # type: ignore[arg-type]


@pytest.mark.parametrize(("m", "ef"), [(2, 64), (100, 200), (16, 31), (16, 513)])
def test_reject_invalid_index_build_settings(m: int, ef: int) -> None:
    with pytest.raises(HnswConfigurationError):
        HnswIndexOptions(dimensions=3, m=m, ef_construction=ef)


def test_benchmark_rejects_invalid_scopes_without_database_access() -> None:
    for bad in (
        {"provider": ""},
        {"model": ""},
        {"top_k": 101},
        {"samples": 0},
        {"samples": 101},
        {"ef_search": 9},
        {"ef_search": 1001},
        {"dimensions": 3072},
    ):
        with pytest.raises(HnswConfigurationError):
            _benchmark_options(**bad)


def test_exact_and_hnsw_queries_share_scope_but_only_approx_can_use_index() -> None:
    opts = _benchmark_options(dimensions=3, top_k=5)
    exact = _retrieval_query(opts, exact=True)
    approx = _retrieval_query(opts, exact=False)
    expected = [
        "d.knowledge_base_id = :knowledge_base_id",
        "dc.chunk_version = d.active_chunk_version",
        "ce.provider = :provider",
        "ce.model = :model",
        "ce.dimensions = 3",
        "ce.embedding::vector(3)",
        "CAST(:query_vector AS vector(3))",
        "LIMIT :top_k",
    ]
    for part in expected:
        assert part in exact
        assert part in approx
    assert "<=>" in approx
    assert "+ 0" in exact
    assert "+ 0" not in approx
    assert "ORDER BY" in exact
    assert "ORDER BY" in approx


def test_planner_detection_uses_actual_index_name_not_optimistic_label() -> None:
    plan = [{"Plan": {"Node Type": "Limit", "Plans": [
        {"Node Type": "Index Scan", "Index Name": "ix_spurel_hnsw_cosine_d3"},
    ]}}]
    assert _plan_uses_index(plan, "ix_spurel_hnsw_cosine_d3")
    assert not _plan_uses_index(plan, "ix_spurel_hnsw_cosine_d1536")
    assert not _plan_uses_index({"Plan": {"Node Type": "Seq Scan"}}, "ix_spurel_hnsw_cosine_d3")
    assert _plan_uses_index(__import__("json").dumps(plan), "ix_spurel_hnsw_cosine_d3")


def test_vector_serialization_rejects_incorrect_dimensions_and_nonfinite() -> None:
    assert _vector_literal("[0.1,0.2,0.3]", 3) == "[0.1,0.2,0.3]"
    assert _vector_literal([0.1, 0.2, 0.3], 3) == "[0.1,0.2,0.3]"
    for value in ("invalid", "[0,1]", "[NaN,1]", [float("inf"), 1], None):
        with pytest.raises(HnswBenchmarkError):
            _vector_literal(value, 3)


def test_benchmark_summary_reports_measured_only_and_no_invented_speedup() -> None:
    opts = _benchmark_options()
    summary = _summarize(
        options=opts,
        size_bytes=4096,
        recalls=[0.5, 1.0, 0.75, 0.75],
        exact_ms=[1.0, 2.0, 4.0, 8.0],
        hnsw_ms=[2.0, 3.0, 5.0, 10.0],
        sampled=4,
    )
    assert summary["mean_recall_at_k"] == 0.75
    assert summary["min_recall_at_k"] == 0.5
    assert summary["exact_median_ms"] == 3.0
    assert summary["hnsw_median_ms"] == 4.0
    assert summary["exact_p95_ms"] == 8.0
    assert summary["hnsw_p95_ms"] == 10.0
    assert summary["planner_used_hnsw"] is True
    assert "self-query bias" in summary["limitations"]
    assert _percentile_95([2.4]) == 2.4


def test_cli_never_builds_an_index_without_explicit_confirmation() -> None:
    output, error = StringIO(), StringIO()
    code = run_hnsw_cli(["build", "--dimensions", "1536"], stdout=output, stderr=error)
    assert code == 3
    assert output.getvalue() == ""
    assert "--confirm-build" in error.getvalue()


def test_cli_rejects_dimension_above_pgvector_hnsw_limit_before_database_access() -> None:
    output, error = StringIO(), StringIO()
    code = run_hnsw_cli(
        ["build", "--dimensions", "3072", "--confirm-build"],
        stdout=output,
        stderr=error,
    )
    assert code == 3
    assert "1–2000" in error.getvalue()
