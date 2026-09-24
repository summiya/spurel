"""Application services for persisted evaluation run history."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.execution import DatasetEvaluationResult
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary
from spurel.evaluation_datasets.run_ports import EvaluationRunRepository

MAX_EVALUATION_RUN_PAGE_SIZE = 100


class EvaluationRunQueryError(ValueError):
    """Raised when evaluation run history parameters are invalid."""


class EvaluationRunNotFoundError(LookupError):
    """Raised when a scoped evaluation run does not exist."""


class DatasetEvaluationExecutor(Protocol):
    """Execution capability wrapped by durable run persistence."""

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        top_k: int,
        candidate_k: int | None = None,
        rrf_k: int | None = None,
    ) -> DatasetEvaluationResult:
        """Execute one dataset benchmark."""
        ...


class EvaluationRunService:
    """Persist and browse immutable evaluation benchmark history."""

    def __init__(self, repository: EvaluationRunRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        knowledge_base_id: UUID,
        result: DatasetEvaluationResult,
    ) -> EvaluationRun:
        """Snapshot and atomically persist one completed benchmark."""
        run = EvaluationRun.from_execution(
            knowledge_base_id=knowledge_base_id,
            result=result,
        )
        await self._repository.add(run)
        return run

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationRunSummary]:
        """Return bounded newest-first benchmark history."""
        _validate_page(limit=limit, offset=offset)
        return await self._repository.list_by_dataset(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        """Return one run only when all scope identifiers match."""
        run = await self._repository.get_by_id(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
        if run is None:
            raise EvaluationRunNotFoundError("evaluation run was not found")
        return run


class PersistedDatasetEvaluationService:
    """Execute a benchmark and persist only fully successful results."""

    def __init__(
        self,
        *,
        executor: DatasetEvaluationExecutor,
        runs: EvaluationRunService,
    ) -> None:
        self._executor = executor
        self._runs = runs

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        top_k: int,
        candidate_k: int | None = None,
        rrf_k: int | None = None,
    ) -> EvaluationRun:
        """Execute first, then persist one immutable successful snapshot."""
        result = await self._executor.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
        )
        return await self._runs.record(
            knowledge_base_id=knowledge_base_id,
            result=result,
        )


def _validate_page(*, limit: int, offset: int) -> None:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAX_EVALUATION_RUN_PAGE_SIZE
    ):
        raise EvaluationRunQueryError(
            "evaluation run page limit is outside the supported range"
        )

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise EvaluationRunQueryError("evaluation run page offset is invalid")
