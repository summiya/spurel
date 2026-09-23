import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
)
from spurel.evaluation_datasets.service import (
    EvaluationDatasetNotFoundError,
    EvaluationDatasetQueryError,
    EvaluationDatasetService,
)
from spurel.retrieval.evaluation import RelevanceJudgment


class FakeEvaluationDatasetRepository:
    def __init__(self) -> None:
        self.datasets: list[EvaluationDataset] = []
        self.cases: list[EvaluationCase] = []
        self.case_summaries: tuple[EvaluationCaseSummary, ...] = ()
        self.dataset_exists = True

    async def add_dataset(self, dataset: EvaluationDataset) -> None:
        self.datasets.append(dataset)

    async def list_datasets(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationDatasetSummary]:
        items = [
            EvaluationDatasetSummary(dataset=item, case_count=0)
            for item in self.datasets
            if item.knowledge_base_id == knowledge_base_id
        ]
        return tuple(items[offset : offset + limit])

    async def add_case(
        self,
        *,
        knowledge_base_id: UUID,
        case: EvaluationCase,
    ) -> bool:
        if not self.dataset_exists:
            return False
        self.cases.append(case)
        return True

    async def list_cases(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationCaseSummary] | None:
        if not self.dataset_exists:
            return None
        return self.case_summaries[offset : offset + limit]

    async def get_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase | None:
        return next(
            (
                case
                for case in self.cases
                if case.dataset_id == dataset_id and case.id == case_id
            ),
            None,
        )


def test_service_creates_dataset_and_atomic_case_input() -> None:
    repository = FakeEvaluationDatasetRepository()
    service = EvaluationDatasetService(repository)
    knowledge_base_id = uuid4()

    dataset = asyncio.run(
        service.create_dataset(
            knowledge_base_id=knowledge_base_id,
            name=" Baseline ",
        )
    )
    case = asyncio.run(
        service.add_case(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset.id,
            query=" auth ",
            judgments=(
                RelevanceJudgment(chunk_id=uuid4(), relevance=2),
            ),
        )
    )

    assert dataset.name == "Baseline"
    assert repository.datasets == [dataset]
    assert case.query == "auth"
    assert repository.cases == [case]


def test_service_returns_not_found_for_unscoped_dataset() -> None:
    repository = FakeEvaluationDatasetRepository()
    repository.dataset_exists = False
    service = EvaluationDatasetService(repository)

    with pytest.raises(EvaluationDatasetNotFoundError):
        asyncio.run(
            service.add_case(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                query="query",
                judgments=(
                    RelevanceJudgment(chunk_id=uuid4(), relevance=1),
                ),
            )
        )


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (50, -1),
        (50, True),
    ],
)
def test_service_rejects_invalid_pagination(limit: int, offset: int) -> None:
    service = EvaluationDatasetService(FakeEvaluationDatasetRepository())

    with pytest.raises(EvaluationDatasetQueryError):
        asyncio.run(
            service.list_datasets(
                knowledge_base_id=uuid4(),
                limit=limit,
                offset=offset,
            )
        )
