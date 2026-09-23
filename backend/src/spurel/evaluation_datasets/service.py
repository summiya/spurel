"""Application services for reusable evaluation datasets."""

from collections.abc import Sequence
from uuid import UUID

from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetRepository
from spurel.retrieval.evaluation import RelevanceJudgment

MAX_EVALUATION_DATASET_PAGE_SIZE = 100


class EvaluationDatasetQueryError(ValueError):
    """Raised when evaluation dataset pagination is invalid."""


class EvaluationDatasetNotFoundError(LookupError):
    """Raised when a scoped evaluation dataset or case does not exist."""


class EvaluationDatasetService:
    """Coordinate evaluation dataset use cases."""

    def __init__(self, repository: EvaluationDatasetRepository) -> None:
        self._repository = repository

    async def create_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        name: str,
    ) -> EvaluationDataset:
        """Create and persist one dataset."""
        dataset = EvaluationDataset.create(
            knowledge_base_id=knowledge_base_id,
            name=name,
        )
        await self._repository.add_dataset(dataset)
        return dataset

    async def list_datasets(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationDatasetSummary]:
        """List a bounded dataset page."""
        _validate_page(limit=limit, offset=offset)
        return await self._repository.list_datasets(
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            offset=offset,
        )

    async def add_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        query: str,
        judgments: tuple[RelevanceJudgment, ...],
    ) -> EvaluationCase:
        """Create and persist one labeled query atomically."""
        case = EvaluationCase.create(
            dataset_id=dataset_id,
            query=query,
            judgments=judgments,
        )
        added = await self._repository.add_case(
            knowledge_base_id=knowledge_base_id,
            case=case,
        )
        if not added:
            raise EvaluationDatasetNotFoundError(
                "evaluation dataset was not found"
            )
        return case

    async def list_cases(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[EvaluationCaseSummary]:
        """List bounded cases for one scoped dataset."""
        _validate_page(limit=limit, offset=offset)
        cases = await self._repository.list_cases(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )
        if cases is None:
            raise EvaluationDatasetNotFoundError(
                "evaluation dataset was not found"
            )
        return cases

    async def get_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase:
        """Return one scoped case with its judgments."""
        case = await self._repository.get_case(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            case_id=case_id,
        )
        if case is None:
            raise EvaluationDatasetNotFoundError(
                "evaluation case was not found"
            )
        return case


def _validate_page(*, limit: int, offset: int) -> None:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAX_EVALUATION_DATASET_PAGE_SIZE
    ):
        raise EvaluationDatasetQueryError(
            "evaluation dataset page limit is outside the supported range"
        )

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise EvaluationDatasetQueryError(
            "evaluation dataset page offset is invalid"
        )
