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
    baseline_run_id: UUID,
) -> list[str]:
    return [
        "--api-base-url",
        "https://spurel.example/api/",
        "--knowledge-base-id",
        str(knowledge_base_id),
        "--dataset-id",
        str(dataset_id),
        "--baseline-run-id",
        str(baseline_run_id),
        "--mode",
        mode.value,
        "--top-k",
        "10",
        "--max-mrr-drop",
        "0.02",
    ]


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
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            {"run_id": str(candidate_run_id)},
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
            baseline_run_id=uuid4(),
        ),
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == int(expected)
    assert f"Candidate evaluation run: {candidate_run_id}" in output.getvalue()
    assert f"Spurel quality gate: {status}" in output.getvalue()


def test_benchmark_gate_runs_candidate_then_gates_against_baseline() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    baseline_run_id = uuid4()
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            {"run_id": str(candidate_run_id)},
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.VECTOR,
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            baseline_run_id=baseline_run_id,
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert len(transport.calls) == 2
    assert transport.calls[0]["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/evaluate/vector"
    )
    assert transport.calls[0]["payload"] == {"top_k": 10}
    assert transport.calls[1]["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/quality-gates/evaluate"
    )
    assert transport.calls[1]["payload"] == {
        "first_run_id": str(baseline_run_id),
        "second_run_id": str(candidate_run_id),
        "thresholds": {"max_mrr_drop": 0.02},
    }


def test_hybrid_benchmark_uses_candidate_and_rrf_configuration() -> None:
    transport = FakeTransport(
        [
            {"run_id": str(uuid4())},
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    code = run_benchmark_gate_cli(
        [
            *_args(
                mode=BenchmarkMode.HYBRID,
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                baseline_run_id=uuid4(),
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


def test_hybrid_benchmark_applies_safe_defaults() -> None:
    transport = FakeTransport(
        [
            {"run_id": str(uuid4())},
            {"status": "pass", "checks": [], "unavailable_metrics": []},
        ]
    )

    run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.HYBRID,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            baseline_run_id=uuid4(),
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


def test_non_hybrid_benchmark_rejects_hybrid_only_configuration() -> None:
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        [
            *_args(
                mode=BenchmarkMode.KEYWORD,
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                baseline_run_id=uuid4(),
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
            "--baseline-run-id",
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


def test_invalid_candidate_run_id_stops_before_quality_gate() -> None:
    transport = FakeTransport([{"run_id": "not-a-uuid"}])
    error = io.StringIO()

    code = run_benchmark_gate_cli(
        _args(
            mode=BenchmarkMode.KEYWORD,
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            baseline_run_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert len(transport.calls) == 1
    assert "invalid run_id" in error.getvalue()


def test_json_output_preserves_candidate_run_id_on_gate_failure() -> None:
    candidate_run_id = uuid4()
    transport = FakeTransport(
        [
            {"run_id": str(candidate_run_id)},
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
                baseline_run_id=uuid4(),
            ),
            "--json",
        ],
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == int(QualityGateCliExitCode.FAIL)
    rendered = output.getvalue()
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
            "--baseline-run-id",
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
