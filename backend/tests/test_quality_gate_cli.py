import io
from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.quality_gate_cli import (
    QualityGateCliExitCode,
    QualityGateCliError,
    run_quality_gate_cli,
)


class FakeTransport:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.last_call: dict[str, object] | None = None

    def post_json(
        self,
        *,
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.last_call = {
            "url": url,
            "payload": payload,
            "headers": headers,
            "timeout_seconds": timeout_seconds,
        }
        return self.response


def _args(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    first_run_id: UUID,
    second_run_id: UUID,
) -> list[str]:
    return [
        "--api-base-url",
        "https://spurel.example/api/",
        "--knowledge-base-id",
        str(knowledge_base_id),
        "--dataset-id",
        str(dataset_id),
        "--first-run-id",
        str(first_run_id),
        "--second-run-id",
        str(second_run_id),
        "--max-mrr-drop",
        "0.03",
        "--max-mean-duration-increase-ms",
        "50",
    ]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("pass", QualityGateCliExitCode.PASS),
        ("fail", QualityGateCliExitCode.FAIL),
        ("not_evaluable", QualityGateCliExitCode.NOT_EVALUABLE),
    ],
)
def test_cli_maps_gate_status_to_stable_exit_code(
    status: str,
    expected: QualityGateCliExitCode,
) -> None:
    transport = FakeTransport(
        {
            "status": status,
            "checks": [],
            "unavailable_metrics": [],
        }
    )
    output = io.StringIO()

    code = run_quality_gate_cli(
        _args(
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            first_run_id=uuid4(),
            second_run_id=uuid4(),
        ),
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == int(expected)
    assert f"Spurel quality gate: {status}" in output.getvalue()


def test_cli_builds_scoped_request_and_threshold_payload() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    first_run_id = uuid4()
    second_run_id = uuid4()
    transport = FakeTransport(
        {
            "status": "pass",
            "checks": [],
            "unavailable_metrics": [],
        }
    )

    code = run_quality_gate_cli(
        _args(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            first_run_id=first_run_id,
            second_run_id=second_run_id,
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert transport.last_call is not None
    assert transport.last_call["url"] == (
        f"https://spurel.example/api/knowledge-bases/{knowledge_base_id}"
        f"/evaluation-datasets/{dataset_id}/quality-gates/evaluate"
    )
    assert transport.last_call["payload"] == {
        "first_run_id": str(first_run_id),
        "second_run_id": str(second_run_id),
        "thresholds": {
            "max_mrr_drop": 0.03,
            "max_mean_duration_increase_ms": 50.0,
        },
    }


def test_cli_uses_optional_bearer_token_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", "secret-token")
    transport = FakeTransport(
        {
            "status": "pass",
            "checks": [],
            "unavailable_metrics": [],
        }
    )

    run_quality_gate_cli(
        _args(
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            first_run_id=uuid4(),
            second_run_id=uuid4(),
        ),
        transport=transport,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert transport.last_call is not None
    headers = transport.last_call["headers"]
    assert headers["Authorization"] == "Bearer secret-token"


def test_cli_json_output_is_machine_readable() -> None:
    response = {
        "status": "fail",
        "checks": [{"metric": "mrr_at_k", "passed": False}],
        "unavailable_metrics": [],
    }
    transport = FakeTransport(response)
    output = io.StringIO()

    code = run_quality_gate_cli(
        [
            *_args(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                first_run_id=uuid4(),
                second_run_id=uuid4(),
            ),
            "--json",
        ],
        transport=transport,
        stdout=output,
        stderr=io.StringIO(),
    )

    assert code == 1
    assert '"status": "fail"' in output.getvalue()


@pytest.mark.parametrize(
    "extra_args",
    [
        [],
        ["--max-mrr-drop", "nan"],
        ["--max-mrr-drop", "1.1"],
        ["--timeout-seconds", "0"],
    ],
)
def test_cli_returns_error_for_invalid_configuration(extra_args: list[str]) -> None:
    base = [
        "--api-base-url",
        "https://spurel.example",
        "--knowledge-base-id",
        str(uuid4()),
        "--dataset-id",
        str(uuid4()),
        "--first-run-id",
        str(uuid4()),
        "--second-run-id",
        str(uuid4()),
    ]

    error = io.StringIO()
    code = run_quality_gate_cli(
        [*base, *extra_args],
        transport=FakeTransport({"status": "pass"}),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "spurel-quality-gate:" in error.getvalue()


def test_cli_returns_error_for_unknown_api_status() -> None:
    error = io.StringIO()

    code = run_quality_gate_cli(
        _args(
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            first_run_id=uuid4(),
            second_run_id=uuid4(),
        ),
        transport=FakeTransport({"status": "unexpected"}),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "supported status" in error.getvalue()


def test_cli_rejects_same_run_ids() -> None:
    run_id = uuid4()
    error = io.StringIO()

    code = run_quality_gate_cli(
        [
            "--api-base-url",
            "https://spurel.example",
            "--knowledge-base-id",
            str(uuid4()),
            "--dataset-id",
            str(uuid4()),
            "--first-run-id",
            str(run_id),
            "--second-run-id",
            str(run_id),
            "--max-mrr-drop",
            "0.01",
        ],
        transport=FakeTransport({"status": "pass"}),
        stdout=io.StringIO(),
        stderr=error,
    )

    assert code == int(QualityGateCliExitCode.ERROR)
    assert "must be different" in error.getvalue()
