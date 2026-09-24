"""Application services for explicit evaluation baselines."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.baseline_domain import (
    MAX_BASELINE_PAGE_SIZE,
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
)
from spurel.evaluation_datasets.baseline_ports import EvaluationBaselineRepository
from spurel.evaluation_datasets.run_domain import EvaluationRun


class EvaluationBaselineNotFoundError(LookupError):
    """Raised when no promoted baseline matches the requested configuration."""


class EvaluationBaselineQueryError(ValueError):
    """Raised when baseline pagination is invalid."""


class EvaluationRunReader(Protocol):
    """Scoped persisted run reader required for baseline promotion."""

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        """Return one scoped persisted evaluation run."""
        ...


class EvaluationBaselineService:
    """Promote and resolve explicit benchmark baselines."""

    def __init__(
        self,
        *,
        repository: EvaluationBaselineRepository,
        runs: EvaluationRunReader,
    ) -> None:
        self._repository = repository
        self._runs = runs

    async def promote(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationBaseline:
        """Promote one scoped run for its exact retrieval configuration."""
        run = await self._runs.get_by_id(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
        baseline = EvaluationBaseline.from_run(run=run)
        return await self._repository.upsert(baseline)

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationBaseline]:
        """List promoted baselines for one dataset."""
        _validate_page(limit=limit, offset=offset)
        return await self._repository.list_by_dataset(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline:
        """Resolve the exact explicitly promoted baseline."""
        configuration.validate()
        baseline = await self._repository.resolve(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            configuration=configuration,
        )
        if baseline is None:
            raise EvaluationBaselineNotFoundError(
                "evaluation baseline was not found"
            )
        return baseline


def _validate_page(*, limit: int, offset: int) -> None:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAX_BASELINE_PAGE_SIZE
    ):
        raise EvaluationBaselineQueryError(
            "evaluation baseline page limit is outside the supported range"
        )

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise EvaluationBaselineQueryError(
            "evaluation baseline page offset is invalid"
        )
