import io
from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.benchmark_gate_cli import (
    BenchmarkMode,
    run_benchmark_gate_cli,
)
from spurel.evaluation_datasets.quality_gate_cli import (
    QualityGateCliError,
    QualityGateCliExitCode,
)


class FakeTransport:
    def __init__(self, responses: list[Mapping[str, object]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post_json(
        self,
        *,
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            raise QualityGateCliError("unexpected extra API call")
        return self.responses.pop(0)


def _args(
    *,
    mode: BenchmarkMode,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    baseline_run_id: UUID | None = None,
) -> list[str]:
    args = [
        "--api-base-url",
        "https://spurel.example/api/",
        "--knowledge-base-id",
        str(knowledge_base_id),
        "--dataset-id",
        str(dataset_id),
        "--mode",
        mode.value,
        "--top-k",
        "10",
        "--max-mrr-drop",
        "0.02",
    ]
    if baseline_run_id is not None:
        args.extend(["--baseline-run-id", str(baseline_run_id)])
    return args


def _candidate(
    *,
    run_id: UUID,
    mode: BenchmarkMode,
    top_k: int = 10,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    embedding_model: str = "text-embedding-3-small",
) -> dict[str, object]:
    uses_embeddings = mode is not BenchmarkMode.KEYWORD
    return {
        "run_id": str(run_id),
        "mode": mode.value,
        "top_k": top_k,
        "candidate_k": candidate_k,
        "rrf_k": rrf_k,
        "embedding_provider": "openai" if uses_embeddings else None,
        "embedding_model": embedding_model if uses_embeddings else None,
        "embedding_dimensions": 1536 if uses_embeddings else None,
    }


def _baseline(*, run_id: UUID) -> dict[str, object]:
    return {"run_id": str(run_id)}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("pass", QualityGateCliExitCode.PASS),
        ("fail", QualityGateCliExitCode.FAIL),
        ("not_evaluable", QualityGateCliExitCode.NOT_EVALUABLE),
    ],
)
def test_benchmark_gate_maps_gate_status_to_stable_exit_code(
    status: str,
    expected: QualityGateCliExitCode,
) -> None:
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(run_id=candidate_run_id, mode=BenchmarkMode.KEYWORD),
            _baseline(run_id=baseline_run_id),
            {
                "status": status,
                "checks": [],
                "unavailable_metrics": [],
            },
        ]
    )
    output = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == int(expected)
    assert (
        f"Baseline evaluation run: {baseline_run_id} (promoted)"
        in output.getvalue()
    )
    assert f"Candidate evaluation run: {candidate_run_id}" in output.getvalue()
    assert f"Spurel quality gate: {status}" in output.getvalue()


def test_auto_baseline_runs_candidate_resolves_exact_config_then_gates() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    candidate = _candidate(
        run_id=candidate_run_id,
        mode=BenchmarkMode.VECTOR,
        embedding_model="server-selected-model",
    )
    transport = FakeTransport(
        [
            candidate,
            _baseline(run_id=baseline_run_id),
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.VECTOR,
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert len(transport.calls) == 3
    assert transport.calls[0]["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/evaluate/vector"
    )
    assert transport.calls[0]["payload"] == {"top_k": 10}

    assert transport.calls[1]["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/baselines/resolve"
    )
    assert transport.calls[1]["payload"] == {
        "mode": "vector",
        "top_k": 10,
        "candidate_k": None,
        "rrf_k": None,
        "embedding_provider": "openai",
        "embedding_model": "server-selected-model",
        "embedding_dimensions": 1536,
    }

    assert transport.calls[2]["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/quality-gates/evaluate"
    )
    assert transport.calls[2]["payload"] == {
        "first_run_id": str(baseline_run_id),
        "second_run_id": str(candidate_run_id),
        "thresholds": {"max_mrr_drop": 0.02},
    }


def test_explicit_baseline_override_skips_promoted_baseline_resolution() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(run_id=candidate_run_id, mode=BenchmarkMode.KEYWORD),
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )
    output = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            baseline_run_id=baseline_run_id,
        ),
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert len(transport.calls) == 2
    assert transport.calls[1]["payload"] == {
        "first_run_id": str(baseline_run_id),
        "second_run_id": str(candidate_run_id),
        "thresholds": {"max_mrr_drop": 0.02},
    }
    assert (
        f"Baseline evaluation run: {baseline_run_id} (explicit)"
        in output.getvalue()
    )


def test_keyword_auto_baseline_resolves_without_embedding_configuration() -> None:
    baseline_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(run_id=uuid4(), mode=BenchmarkMode.KEYWORD),
            _baseline(run_id=baseline_run_id),
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert transport.calls[1]["payload"] == {
        "mode": "keyword",
        "top_k": 10,
        "candidate_k": None,
        "rrf_k": None,
        "embedding_provider": None,
        "embedding_model": None,
        "embedding_dimensions": None,
    }


def test_hybrid_benchmark_resolves_exact_candidate_and_rrf_config() -> None:
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(
                run_id=candidate_run_id,
                mode=BenchmarkMode.HYBRID,
                candidate_k=40,
                rrf_k=80,
            ),
            _baseline(run_id=baseline_run_id),
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    code = run_benchmark_gate_cli(
        [
            *_args(
                mode=BenchmarkMode.HYBRID,
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
            ),
            "--candidate-k",
            "40",
            "--rrf-k",
            "80",
        ],
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert transport.calls[0]["payload"] == {
        "top_k": 10,
        "candidate_k": 40,
        "rrf_k": 80,
    }
    assert transport.calls[1]["payload"]["candidate_k"] == 40
    assert transport.calls[1]["payload"]["rrf_k"] == 80


def test_hybrid_benchmark_applies_safe_defaults() -> None:
    transport = FakeTransport(
        [
            _candidate(
                run_id=uuid4(),
                mode=BenchmarkMode.HYBRID,
                candidate_k=50,
                rrf_k=60,
            ),
            _baseline(run_id=uuid4()),
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.HYBRID,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert transport.calls[0]["payload"] == {
        "top_k": 10,
        "candidate_k": 50,
        "rrf_k": 60,
    }


def test_candidate_response_config_mismatch_stops_before_baseline_lookup() -> None:
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(
                run_id=candidate_run_id,
                mode=BenchmarkMode.VECTOR,
                top_k=20,
            )
        ]
    )
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.VECTOR,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert len(transport.calls) == 1
    assert f"Candidate evaluation run: {candidate_run_id}" in error.getvalue()
    assert "top_k does not match" in error.getvalue()


def test_invalid_promoted_baseline_run_id_stops_before_quality_gate() -> None:
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(run_id=candidate_run_id, mode=BenchmarkMode.KEYWORD),
            {"run_id": "not-a-uuid"},
        ]
    )
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert len(transport.calls) == 2
    assert f"Candidate evaluation run: {candidate_run_id}" in error.getvalue()
    assert "promoted baseline response contained an invalid run_id" in error.getvalue()


def test_non_hybrid_benchmark_rejects_hybrid_only_configuration() -> None:
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        [
            *_args(
                mode=BenchmarkMode.KEYWORD,
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
            ),
            "--candidate-k",
            "40",
        ],
        transport=FakeTransport([]),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "only valid with --mode hybrid" in error.getvalue()


def test_hybrid_candidate_pool_must_cover_top_k() -> None:
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        [
            "--api-base-url",
            "https://spurel.example",
            "--knowledge-base-id",
            str(uuid4()),
            "--dataset-id",
            str(uuid4()),
            "--mode",
            "hybrid",
            "--top-k",
            "50",
            "--candidate-k",
            "20",
            "--max-mrr-drop",
            "0.02",
        ],
        transport=FakeTransport([]),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "greater than or equal to --top-k" in error.getvalue()


def test_invalid_candidate_run_id_stops_before_baseline_lookup() -> None:
    transport = FakeTransport(
        [
            {
                **_candidate(run_id=uuid4(), mode=BenchmarkMode.KEYWORD),
                "run_id": "not-a-uuid",
            }
        ]
    )
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert len(transport.calls) == 1
    assert "invalid run_id" in error.getvalue()


def test_json_output_reports_resolved_baseline_and_candidate_on_gate_failure() -> None:
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            _candidate(run_id=candidate_run_id, mode=BenchmarkMode.KEYWORD),
            _baseline(run_id=baseline_run_id),
            {
                "status": "fail",
                "checks": [{"metric": "mrr_at_k", "passed": False}],
                "unavailable_metrics": [],
            },
        ]
    )
    output = io.StringIO()

    code = run_benchmark_gate_cli(
        [
            *_args(
                mode=BenchmarkMode.KEYWORD,
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
            ),
            "--json",
        ],
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == int(QualityGateCliExitCode.FAIL)
    rendered = output.getvalue()
    assert f'"baseline_run_id": "{baseline_run_id}"' in rendered
    assert '"baseline_source": "promoted"' in rendered
    assert f'"candidate_run_id": "{candidate_run_id}"' in rendered
    assert '"status": "fail"' in rendered


def test_benchmark_gate_refuses_token_over_plain_http(monkeypatch) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", "secret-token")
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        [
            "--api-base-url",
            "http://spurel.example",
            "--knowledge-base-id",
            str(uuid4()),
            "--dataset-id",
            str(uuid4()),
            "--mode",
            "keyword",
            "--max-mrr-drop",
            "0.01",
        ],
        transport=FakeTransport([]),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "requires an https:// API base URL" in error.getvalue()
