"""One-command CI benchmark execution followed by a quality gate."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from spurel.evaluation_datasets.quality_gate_cli import (
    JsonHttpTransport,
    QualityGateCliError,
    QualityGateCliExitCode,
    UrllibJsonHttpTransport,
)

DEFAULT_BENCHMARK_TIMEOUT_SECONDS = 300.0
_BEARER_TOKEN_ENV = "SPUREL_API_TOKEN"


class BenchmarkMode(StrEnum):
    """Supported persisted dataset benchmark modes."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class _BenchmarkArgumentParser(argparse.ArgumentParser):
    """Argument parser preserving the stable CI error exit code."""

    def error(self, message: str) -> None:
        raise QualityGateCliError(message)


@dataclass(frozen=True, slots=True)
class BenchmarkGateCliConfig:
    """Validated one-command benchmark + quality-gate configuration."""

    api_base_url: str
    knowledge_base_id: UUID
    dataset_id: UUID
    baseline_run_id: UUID
    mode: BenchmarkMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    thresholds: Mapping[str, float]
    timeout_seconds: float
    json_output: bool

    @property
    def dataset_base_url(self) -> str:
        base = self.api_base_url.rstrip("/")
        return (
            f"{base}/knowledge-bases/{self.knowledge_base_id}"
            f"/evaluation-datasets/{self.dataset_id}"
        )

    @property
    def evaluation_endpoint(self) -> str:
        return f"{self.dataset_base_url}/evaluate/{self.mode.value}"

    @property
    def quality_gate_endpoint(self) -> str:
        return f"{self.dataset_base_url}/quality-gates/evaluate"


def run_benchmark_gate_cli(
    argv: Sequence[str] | None = None,
    *,
    transport: JsonHttpTransport | None = None,
    stdout=None,
    stderr=None,
) -> int:
    """Run a candidate benchmark, then gate it against a baseline run."""
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr

    try:
        config = _parse_config(argv)
        _validate_transport_security(config)

        client = transport or UrllibJsonHttpTransport()
        headers = _request_headers()

        candidate = client.post_json(
            url=config.evaluation_endpoint,
            payload=_evaluation_payload(config),
            headers=headers,
            timeout_seconds=config.timeout_seconds,
        )
        candidate_run_id = _candidate_run_id(candidate)

        if candidate_run_id == config.baseline_run_id:
            raise QualityGateCliError(
                "candidate benchmark returned the configured baseline run ID"
            )

        gate = client.post_json(
            url=config.quality_gate_endpoint,
            payload={
                "first_run_id": str(config.baseline_run_id),
                "second_run_id": str(candidate_run_id),
                "thresholds": dict(config.thresholds),
            },
            headers=headers,
            timeout_seconds=config.timeout_seconds,
        )
        exit_code = _exit_code_from_gate(gate)

        if config.json_output:
            print(
                json.dumps(
                    {
                        "candidate_run_id": str(candidate_run_id),
                        "quality_gate": gate,
                    },
                    sort_keys=True,
                ),
                file=output,
            )
        else:
            _print_human_summary(
                candidate_run_id=candidate_run_id,
                gate=gate,
                output=output,
            )

        return int(exit_code)
    except QualityGateCliError as exc:
        print(f"spurel-benchmark-gate: {exc}", file=error_output)
        return int(QualityGateCliExitCode.ERROR)


def main() -> None:
    """Console-script entrypoint."""
    raise SystemExit(run_benchmark_gate_cli())


def _parse_config(argv: Sequence[str] | None) -> BenchmarkGateCliConfig:
    parser = _BenchmarkArgumentParser(
        prog="spurel-benchmark-gate",
        description=(
            "Create a persisted candidate evaluation run, compare it with a "
            "baseline run, and return a CI-friendly quality-gate exit code."
        ),
    )

    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--knowledge-base-id", required=True, type=UUID)
    parser.add_argument("--dataset-id", required=True, type=UUID)
    parser.add_argument("--baseline-run-id", required=True, type=UUID)
    parser.add_argument(
        "--mode",
        required=True,
        type=BenchmarkMode,
        choices=list(BenchmarkMode),
    )
    parser.add_argument("--top-k", type=_bounded_integer(1, 100), default=10)
    parser.add_argument("--candidate-k", type=_bounded_integer(1, 100))
    parser.add_argument("--rrf-k", type=_bounded_integer(1, 1_000))

    parser.add_argument("--max-mean-precision-drop", type=_unit_interval)
    parser.add_argument("--max-mean-recall-drop", type=_unit_interval)
    parser.add_argument("--max-mrr-drop", type=_unit_interval)
    parser.add_argument("--max-mean-ndcg-drop", type=_unit_interval)
    parser.add_argument("--max-mean-judgment-coverage-drop", type=_unit_interval)
    parser.add_argument("--max-mean-duration-increase-ms", type=_non_negative_float)

    parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=DEFAULT_BENCHMARK_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print candidate run ID plus quality-gate response as JSON.",
    )

    args = parser.parse_args(argv)
    thresholds = _thresholds(args)
    if not thresholds:
        raise QualityGateCliError(
            "at least one quality-gate threshold must be provided"
        )

    api_base_url = args.api_base_url.strip()
    if not api_base_url.startswith(("http://", "https://")):
        raise QualityGateCliError(
            "--api-base-url must start with http:// or https://"
        )

    candidate_k = args.candidate_k
    rrf_k = args.rrf_k

    if args.mode is BenchmarkMode.HYBRID:
        candidate_k = 50 if candidate_k is None else candidate_k
        rrf_k = 60 if rrf_k is None else rrf_k
        if candidate_k < args.top_k:
            raise QualityGateCliError(
                "--candidate-k must be greater than or equal to --top-k"
            )
    elif candidate_k is not None or rrf_k is not None:
        raise QualityGateCliError(
            "--candidate-k and --rrf-k are only valid with --mode hybrid"
        )

    return BenchmarkGateCliConfig(
        api_base_url=api_base_url,
        knowledge_base_id=args.knowledge_base_id,
        dataset_id=args.dataset_id,
        baseline_run_id=args.baseline_run_id,
        mode=args.mode,
        top_k=args.top_k,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        thresholds=thresholds,
        timeout_seconds=args.timeout_seconds,
        json_output=args.json_output,
    )


def _thresholds(args: argparse.Namespace) -> dict[str, float]:
    return {
        key: value
        for key, value in {
            "max_mean_precision_drop": args.max_mean_precision_drop,
            "max_mean_recall_drop": args.max_mean_recall_drop,
            "max_mrr_drop": args.max_mrr_drop,
            "max_mean_ndcg_drop": args.max_mean_ndcg_drop,
            "max_mean_judgment_coverage_drop": (
                args.max_mean_judgment_coverage_drop
            ),
            "max_mean_duration_increase_ms": (
                args.max_mean_duration_increase_ms
            ),
        }.items()
        if value is not None
    }


def _evaluation_payload(config: BenchmarkGateCliConfig) -> dict[str, int]:
    payload = {"top_k": config.top_k}
    if config.mode is BenchmarkMode.HYBRID:
        assert config.candidate_k is not None
        assert config.rrf_k is not None
        payload["candidate_k"] = config.candidate_k
        payload["rrf_k"] = config.rrf_k
    return payload


def _candidate_run_id(response: Mapping[str, object]) -> UUID:
    raw_run_id = response.get("run_id")
    if not isinstance(raw_run_id, str):
        raise QualityGateCliError(
            "candidate evaluation response did not contain a run_id"
        )

    try:
        return UUID(raw_run_id)
    except ValueError as exc:
        raise QualityGateCliError(
            "candidate evaluation response contained an invalid run_id"
        ) from exc


def _exit_code_from_gate(
    response: Mapping[str, object],
) -> QualityGateCliExitCode:
    status = response.get("status")
    if status == "pass":
        return QualityGateCliExitCode.PASS
    if status == "fail":
        return QualityGateCliExitCode.FAIL
    if status == "not_evaluable":
        return QualityGateCliExitCode.NOT_EVALUABLE
    raise QualityGateCliError(
        "quality gate response did not contain a supported status"
    )


def _print_human_summary(
    *,
    candidate_run_id: UUID,
    gate: Mapping[str, object],
    output,
) -> None:
    print(f"Candidate evaluation run: {candidate_run_id}", file=output)
    print(f"Spurel quality gate: {gate.get('status')}", file=output)

    checks = gate.get("checks")
    if isinstance(checks, list):
        for raw_check in checks:
            if not isinstance(raw_check, dict):
                continue
            marker = "PASS" if raw_check.get("passed") is True else "FAIL"
            print(
                f"- {marker} {raw_check.get('metric')}: "
                f"delta={raw_check.get('delta')}, "
                f"regression={raw_check.get('regression_amount')}, "
                f"allowed={raw_check.get('allowed_regression')}",
                file=output,
            )

    unavailable = gate.get("unavailable_metrics")
    if isinstance(unavailable, list) and unavailable:
        print(
            "- unavailable: " + ", ".join(str(value) for value in unavailable),
            file=output,
        )


def _request_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "spurel-benchmark-gate",
    }
    token = os.getenv(_BEARER_TOKEN_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _validate_transport_security(config: BenchmarkGateCliConfig) -> None:
    if os.getenv(_BEARER_TOKEN_ENV) and not config.api_base_url.startswith("https://"):
        raise QualityGateCliError(
            "SPUREL_API_TOKEN requires an https:// API base URL"
        )


def _bounded_integer(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc

        if parsed < minimum or parsed > maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def _unit_interval(value: str) -> float:
    parsed = _float(value)
    if parsed < 0 or parsed > 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = _float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _positive_float(value: str) -> float:
    parsed = _float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc

    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a finite number")
    return parsed
