"""Explicit promoted baselines for evaluation datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_domain import EvaluationRun

MAX_BASELINE_PAGE_SIZE = 100


class EvaluationBaselineConfigurationError(ValueError):
    """Raised when a baseline retrieval configuration is invalid."""


@dataclass(frozen=True, slots=True)
class EvaluationBaselineConfiguration:
    """Exact retrieval configuration used to identify one promoted baseline."""

    mode: DatasetEvaluationMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None

    @classmethod
    def from_run(cls, run: EvaluationRun) -> "EvaluationBaselineConfiguration":
        """Capture the exact persisted retrieval configuration from a run."""
        return cls(
            mode=run.mode,
            top_k=run.top_k,
            candidate_k=run.candidate_k,
            rrf_k=run.rrf_k,
            embedding_provider=run.embedding_provider,
            embedding_model=run.embedding_model,
            embedding_dimensions=run.embedding_dimensions,
        )

    def validate(self) -> None:
        """Validate the same configuration invariants enforced by evaluation runs."""
        if (
            isinstance(self.top_k, bool)
            or not isinstance(self.top_k, int)
            or self.top_k < 1
            or self.top_k > 100
        ):
            raise EvaluationBaselineConfigurationError(
                "baseline top_k is outside the supported range"
            )

        if self.mode is DatasetEvaluationMode.HYBRID:
            if (
                isinstance(self.candidate_k, bool)
                or not isinstance(self.candidate_k, int)
                or self.candidate_k < self.top_k
                or self.candidate_k > 100
            ):
                raise EvaluationBaselineConfigurationError(
                    "hybrid baseline candidate_k is invalid"
                )
            if (
                isinstance(self.rrf_k, bool)
                or not isinstance(self.rrf_k, int)
                or self.rrf_k < 1
                or self.rrf_k > 1_000
            ):
                raise EvaluationBaselineConfigurationError(
                    "hybrid baseline rrf_k is invalid"
                )
        elif self.candidate_k is not None or self.rrf_k is not None:
            raise EvaluationBaselineConfigurationError(
                "non-hybrid baseline cannot contain hybrid configuration"
            )

        embedding_values = (
            self.embedding_provider,
            self.embedding_model,
            self.embedding_dimensions,
        )
        complete_embedding_space = all(value is not None for value in embedding_values)

        if self.mode in {DatasetEvaluationMode.VECTOR, DatasetEvaluationMode.HYBRID}:
            if not complete_embedding_space:
                raise EvaluationBaselineConfigurationError(
                    "vector-based baseline requires embedding configuration"
                )

            assert self.embedding_provider is not None
            assert self.embedding_model is not None
            assert self.embedding_dimensions is not None
            if (
                not self.embedding_provider.strip()
                or not self.embedding_model.strip()
                or isinstance(self.embedding_dimensions, bool)
                or not isinstance(self.embedding_dimensions, int)
                or self.embedding_dimensions < 1
            ):
                raise EvaluationBaselineConfigurationError(
                    "baseline embedding configuration is invalid"
                )
        elif any(value is not None for value in embedding_values):
            raise EvaluationBaselineConfigurationError(
                "keyword baseline cannot contain embedding configuration"
            )

    @property
    def fingerprint(self) -> str:
        """Return a stable SHA-256 key for exact configuration equality."""
        self.validate()
        canonical = json.dumps(
            {
                "mode": self.mode.value,
                "top_k": self.top_k,
                "candidate_k": self.candidate_k,
                "rrf_k": self.rrf_k,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": self.embedding_dimensions,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluationBaseline:
    """Explicit promoted run for one dataset retrieval configuration."""

    id: UUID
    knowledge_base_id: UUID
    dataset_id: UUID
    run_id: UUID
    configuration: EvaluationBaselineConfiguration
    configuration_fingerprint: str
    promoted_at: datetime

    @classmethod
    def from_run(
        cls,
        *,
        run: EvaluationRun,
        baseline_id: UUID | None = None,
        promoted_at: datetime | None = None,
    ) -> "EvaluationBaseline":
        """Create a promoted baseline snapshot from one persisted run."""
        configuration = EvaluationBaselineConfiguration.from_run(run)
        return cls(
            id=baseline_id or uuid4(),
            knowledge_base_id=run.knowledge_base_id,
            dataset_id=run.dataset_id,
            run_id=run.id,
            configuration=configuration,
            configuration_fingerprint=configuration.fingerprint,
            promoted_at=promoted_at or datetime.now(UTC),
        )
