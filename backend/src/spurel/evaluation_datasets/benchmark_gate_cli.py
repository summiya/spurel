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


class BenchmarkBaselineSource(StrEnum):
    """How the baseline run was selected."""

    EXPLICIT = "explicit"
    PROMOTED = "promoted"


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
    baseline_run_id: UUID | None
    mode: BenchmarkMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    thresholds: Mapping[str, float]
    promote_on_pass: bool
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
    def baseline_resolve_endpoint(self) -> str:
        return f"{self.dataset_base_url}/baselines/resolve"

    @property
    def baseline_promote_endpoint(self) -> str:
        return f"{self.dataset_base_url}/baselines"

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
    """Run a candidate benchmark, resolve its baseline, then quality-gate it."""
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    candidate_run_id: UUID | None = None

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
        _validate_candidate_response(candidate=candidate, config=config)

        baseline_run_id, baseline_source = _resolve_baseline_run(
            config=config,
            candidate=candidate,
            client=client,
            headers=headers,
        )

        if candidate_run_id == baseline_run_id:
            raise QualityGateCliError(
                "candidate benchmark resolved to the same run as its baseline"
            )

        gate = client.post_json(
            url=config.quality_gate_endpoint,
            payload={
                "first_run_id": str(baseline_run_id),
                "second_run_id": str(candidate_run_id),
                "thresholds": dict(config.thresholds),
            },
            headers=headers,
            timeout_seconds=config.timeout_seconds,
        )
        exit_code = _exit_code_from_gate(gate)
        promoted = False

        if (
            exit_code == QualityGateCliExitCode.PASS
            and config.promote_on_pass
        ):
            promoted = _promote_candidate_baseline(
                config=config,
                candidate_run_id=candidate_run_id,
                client=client,
                headers=headers,
            )

        if config.json_output:
            print(
                json.dumps(
                    {
                        "baseline_run_id": str(baseline_run_id),
                        "baseline_source": baseline_source.value,
                        "candidate_run_id": str(candidate_run_id),
                        "candidate_promoted": promoted,
                        "quality_gate": gate,
                    },
                    sort_keys=True,
                ),
                file=output,
            )
        else:
            _print_human_summary(
                baseline_run_id=baseline_run_id,
                baseline_source=baseline_source,
                candidate_run_id=candidate_run_id,
                promoted=promoted,
                gate=gate,
                output=output,
            )

        return int(exit_code)
    except QualityGateCliError as exc:
        if candidate_run_id is not None:
            print(
                f"Candidate evaluation run: {candidate_run_id}",
                file=error_output,
            )
        print(f"spurel-benchmark-gate: {exc}", file=error_output)
        return int(QualityGateCliExitCode.ERROR)


def main() -> None:
    """Console-script entrypoint."""
    raise SystemExit(run_benchmark_gate_cli())


def _parse_config(argv: Sequence[str] | None) -> BenchmarkGateCliConfig:
    parser = _BenchmarkArgumentParser(
        prog="spurel-benchmark-gate",
        description=(
            "Create a persisted candidate evaluation run, resolve its promoted "
            "baseline or use an explicit baseline override, and return a "
            "CI-friendly quality-gate exit code."
        ),
    )

    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--knowledge-base-id", required=True, type=UUID)
    parser.add_argument("--dataset-id", required=True, type=UUID)
    parser.add_argument(
        "--baseline-run-id",
        type=UUID,
        help=(
            "Optional explicit baseline override. When omitted, Spurel resolves "
            "the promoted baseline for the candidate's exact persisted config."
        ),
    )
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
        "--promote-on-pass",
        action="store_true",
        help=(
            "Promote the persisted candidate as the new baseline only after "
            "the quality gate returns pass."
        ),
    )

    parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=DEFAULT_BENCHMARK_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help=(
            "Print baseline source/run, candidate run, and quality-gate "
            "response as JSON."
        ),
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
        promote_on_pass=args.promote_on_pass,
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


def _resolve_baseline_run(
    *,
    config: BenchmarkGateCliConfig,
    candidate: Mapping[str, object],
    client: JsonHttpTransport,
    headers: Mapping[str, str],
) -> tuple[UUID, BenchmarkBaselineSource]:
    if config.baseline_run_id is not None:
        return config.baseline_run_id, BenchmarkBaselineSource.EXPLICIT

    baseline = client.post_json(
        url=config.baseline_resolve_endpoint,
        payload=_candidate_baseline_configuration(candidate),
        headers=headers,
        timeout_seconds=config.timeout_seconds,
    )
    return _baseline_run_id(baseline), BenchmarkBaselineSource.PROMOTED


def _candidate_baseline_configuration(
    candidate: Mapping[str, object],
) -> dict[str, object]:
    required_keys = (
        "mode",
        "top_k",
        "candidate_k",
        "rrf_k",
        "embedding_provider",
        "embedding_model",
        "embedding_dimensions",
    )
    missing = [key for key in required_keys if key not in candidate]
    if missing:
        raise QualityGateCliError(
            "candidate evaluation response did not contain complete "
            "retrieval configuration"
        )

    return {key: candidate[key] for key in required_keys}


def _candidate_run_id(response: Mapping[str, object]) -> UUID:
    return _uuid_field(
        response=response,
        field="run_id",
        context="candidate evaluation",
    )


def _baseline_run_id(response: Mapping[str, object]) -> UUID:
    return _uuid_field(
        response=response,
        field="run_id",
        context="promoted baseline",
    )


def _uuid_field(
    *,
    response: Mapping[str, object],
    field: str,
    context: str,
) -> UUID:
    raw_value = response.get(field)
    if not isinstance(raw_value, str):
        raise QualityGateCliError(
            f"{context} response did not contain a {field}"
        )

    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise QualityGateCliError(
            f"{context} response contained an invalid {field}"
        ) from exc


def _validate_candidate_response(
    *,
    candidate: Mapping[str, object],
    config: BenchmarkGateCliConfig,
) -> None:
    mode = candidate.get("mode")
    top_k = candidate.get("top_k")

    if mode != config.mode.value:
        raise QualityGateCliError(
            "candidate evaluation response mode does not match the request"
        )
    if top_k != config.top_k:
        raise QualityGateCliError(
            "candidate evaluation response top_k does not match the request"
        )

    candidate_k = candidate.get("candidate_k")
    rrf_k = candidate.get("rrf_k")
    if candidate_k != config.candidate_k or rrf_k != config.rrf_k:
        raise QualityGateCliError(
            "candidate evaluation response retrieval config does not match "
            "the request"
        )

    embedding_provider = candidate.get("embedding_provider")
    embedding_model = candidate.get("embedding_model")
    embedding_dimensions = candidate.get("embedding_dimensions")

    if config.mode is BenchmarkMode.KEYWORD:
        if any(
            value is not None
            for value in (
                embedding_provider,
                embedding_model,
                embedding_dimensions,
            )
        ):
            raise QualityGateCliError(
                "keyword candidate unexpectedly returned embedding config"
            )
        return

    if (
        not isinstance(embedding_provider, str)
        or not embedding_provider.strip()
        or not isinstance(embedding_model, str)
        or not embedding_model.strip()
        or isinstance(embedding_dimensions, bool)
        or not isinstance(embedding_dimensions, int)
        or embedding_dimensions < 1
    ):
        raise QualityGateCliError(
            "candidate evaluation response embedding config is invalid"
        )


def _promote_candidate_baseline(
    *,
    config: BenchmarkGateCliConfig,
    candidate_run_id: UUID,
    client: JsonHttpTransport,
    headers: Mapping[str, str],
) -> bool:
    baseline = client.put_json(
        url=config.baseline_promote_endpoint,
        payload={"run_id": str(candidate_run_id)},
        headers=headers,
        timeout_seconds=config.timeout_seconds,
    )
    promoted_run_id = _uuid_field(
        response=baseline,
        field="run_id",
        context="baseline promotion",
    )
    if promoted_run_id != candidate_run_id:
        raise QualityGateCliError(
            "baseline promotion response did not reference the candidate run"
        )
    return True


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
    baseline_run_id: UUID,
    baseline_source: BenchmarkBaselineSource,
    candidate_run_id: UUID,
    promoted: bool,
    gate: Mapping[str, object],
    output,
) -> None:
    print(
        f"Baseline evaluation run: {baseline_run_id} "
        f"({baseline_source.value})",
        file=output,
    )
    print(f"Candidate evaluation run: {candidate_run_id}", file=output)
    print(f"Spurel quality gate: {gate.get('status')}", file=output)
    if promoted:
        print("Candidate promoted as baseline: yes", file=output)

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
    if (
        os.getenv(_BEARER_TOKEN_ENV)
        and not config.api_base_url.startswith("https://")
    ):
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
