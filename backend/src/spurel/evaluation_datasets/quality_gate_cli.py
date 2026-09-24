"""CI-friendly command-line client for Spurel benchmark quality gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

DEFAULT_TIMEOUT_SECONDS = 30.0
_BEARER_TOKEN_ENV = "SPUREL_API_TOKEN"


class QualityGateCliExitCode(IntEnum):
    """Stable process exit codes for CI integrations."""

    PASS = 0
    FAIL = 1
    NOT_EVALUABLE = 2
    ERROR = 3


class QualityGateCliError(RuntimeError):
    """Raised when the CLI cannot evaluate a gate safely."""


class _QualityGateArgumentParser(argparse.ArgumentParser):
    """Argument parser that preserves the CLI's stable error exit code."""

    def error(self, message: str) -> None:
        raise QualityGateCliError(message)


class JsonHttpTransport(Protocol):
    """Minimal HTTP capability required by the CLI."""

    def post_json(
        self,
        *,
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """POST JSON and return a decoded JSON object."""
        ...


class UrllibJsonHttpTransport:
    """Standard-library JSON HTTP transport."""

    def post_json(
        self,
        *,
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = _safe_http_error_detail(exc)
            raise QualityGateCliError(
                f"quality gate API returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise QualityGateCliError(
                "quality gate API could not be reached"
            ) from exc
        except TimeoutError as exc:
            raise QualityGateCliError("quality gate API request timed out") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QualityGateCliError(
                "quality gate API returned invalid JSON"
            ) from exc

        if not isinstance(decoded, dict):
            raise QualityGateCliError(
                "quality gate API returned an unexpected JSON shape"
            )
        return decoded


@dataclass(frozen=True, slots=True)
class QualityGateCliConfig:
    """Validated CLI configuration."""

    api_base_url: str
    knowledge_base_id: UUID
    dataset_id: UUID
    first_run_id: UUID
    second_run_id: UUID
    thresholds: Mapping[str, float]
    timeout_seconds: float
    json_output: bool

    @property
    def endpoint(self) -> str:
        base = self.api_base_url.rstrip("/")
        return (
            f"{base}/knowledge-bases/{self.knowledge_base_id}"
            f"/evaluation-datasets/{self.dataset_id}"
            "/quality-gates/evaluate"
        )


def run_quality_gate_cli(
    argv: Sequence[str] | None = None,
    *,
    transport: JsonHttpTransport | None = None,
    stdout=None,
    stderr=None,
) -> int:
    """Execute the CLI and return a stable CI process exit code."""
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr

    try:
        config = _parse_config(argv)
        response = (transport or UrllibJsonHttpTransport()).post_json(
            url=config.endpoint,
            payload={
                "first_run_id": str(config.first_run_id),
                "second_run_id": str(config.second_run_id),
                "thresholds": dict(config.thresholds),
            },
            headers=_request_headers(),
            timeout_seconds=config.timeout_seconds,
        )
        exit_code = _exit_code_from_response(response)

        if config.json_output:
            print(json.dumps(response, sort_keys=True), file=output)
        else:
            _print_human_summary(response=response, output=output)

        return int(exit_code)
    except QualityGateCliError as exc:
        print(f"spurel-quality-gate: {exc}", file=error_output)
        return int(QualityGateCliExitCode.ERROR)


def main() -> None:
    """Console-script entrypoint."""
    raise SystemExit(run_quality_gate_cli())


def _parse_config(argv: Sequence[str] | None) -> QualityGateCliConfig:
    parser = _QualityGateArgumentParser(
        prog="spurel-quality-gate",
        description=(
            "Evaluate a persisted Spurel benchmark quality gate and return "
            "CI-friendly exit codes."
        ),
    )
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--knowledge-base-id", required=True, type=UUID)
    parser.add_argument("--dataset-id", required=True, type=UUID)
    parser.add_argument("--first-run-id", required=True, type=UUID)
    parser.add_argument("--second-run-id", required=True, type=UUID)

    parser.add_argument("--max-mean-precision-drop", type=_unit_interval)
    parser.add_argument("--max-mean-recall-drop", type=_unit_interval)
    parser.add_argument("--max-mrr-drop", type=_unit_interval)
    parser.add_argument("--max-mean-ndcg-drop", type=_unit_interval)
    parser.add_argument("--max-mean-judgment-coverage-drop", type=_unit_interval)
    parser.add_argument("--max-mean-duration-increase-ms", type=_non_negative_float)

    parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the API response as one JSON object.",
    )

    args = parser.parse_args(argv)
    thresholds = {
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

    if not thresholds:
        raise QualityGateCliError(
            "at least one quality-gate threshold must be provided"
        )

    api_base_url = args.api_base_url.strip()
    if not api_base_url.startswith(("http://", "https://")):
        raise QualityGateCliError(
            "--api-base-url must start with http:// or https://"
        )

    if args.first_run_id == args.second_run_id:
        raise QualityGateCliError(
            "--first-run-id and --second-run-id must be different"
        )

    return QualityGateCliConfig(
        api_base_url=api_base_url,
        knowledge_base_id=args.knowledge_base_id,
        dataset_id=args.dataset_id,
        first_run_id=args.first_run_id,
        second_run_id=args.second_run_id,
        thresholds=thresholds,
        timeout_seconds=args.timeout_seconds,
        json_output=args.json_output,
    )


def _request_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "spurel-quality-gate",
    }
    token = os.getenv(_BEARER_TOKEN_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _exit_code_from_response(
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
        "quality gate API response did not contain a supported status"
    )


def _print_human_summary(
    *,
    response: Mapping[str, object],
    output,
) -> None:
    status = response.get("status")
    print(f"Spurel quality gate: {status}", file=output)

    checks = response.get("checks")
    if isinstance(checks, list):
        for raw_check in checks:
            if not isinstance(raw_check, dict):
                continue
            metric = raw_check.get("metric")
            passed = raw_check.get("passed")
            delta = raw_check.get("delta")
            regression = raw_check.get("regression_amount")
            allowed = raw_check.get("allowed_regression")
            marker = "PASS" if passed is True else "FAIL"
            print(
                f"- {marker} {metric}: delta={delta}, "
                f"regression={regression}, allowed={allowed}",
                file=output,
            )

    unavailable = response.get("unavailable_metrics")
    if isinstance(unavailable, list) and unavailable:
        print(
            "- unavailable: " + ", ".join(str(value) for value in unavailable),
            file=output,
        )


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


def _safe_http_error_detail(exc: HTTPError) -> str:
    try:
        raw = exc.read()
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                return detail
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        pass
    return "request failed"
