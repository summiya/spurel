import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.execution import (
    DatasetEvaluationCaseResult,
    DatasetEvaluationMode,
    DatasetEvaluationResult,
)
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError
from spurel.evaluation_datasets.run_service import (
    EvaluationRunNotFoundError,
    EvaluationRunQueryError,
    EvaluationRunService,
    PersistedDatasetEvaluationService,
)
from spurel.retrieval.evaluation import RetrievalMetricValues


class FakeRunRepository:
    def __init__(self) -> None:
        self.saved: list[EvaluationRun] = []
        self.summaries: tuple[EvaluationRunSummary, ...] = ()
        self.run: EvaluationRun | None = None
        self.fail_add = False

    async def add(self, run: EvaluationRun) -> None:
        if self.fail_add:
            raise EvaluationRunPersistenceError("database detail")
        self.saved.append(run)
        self.run = run

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationRunSummary]:
        return self.summaries[offset : offset + limit]

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun | None:
        if (
            self.run is not None
            and self.run.id == run_id
            and self.run.knowledge_base_id == knowledge_base_id
            and self.run.dataset_id == dataset_id
        ):
            return self.run
        return None


class FakeExecutor:
    def __init__(self, result: DatasetEvaluationResult) -> None:
        self.result = result
        self.calls = 0

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        top_k: int,
        candidate_k: int | None = None,
        rrf_k: int | None = None,
    ) -> DatasetEvaluationResult:
        self.calls += 1
        return self.result


def _result(*, dataset_id: UUID) -> DatasetEvaluationResult:
    metrics = RetrievalMetricValues(
        cutoff=10,
        judged_count=2,
        relevant_count=1,
        retrieved_count_at_k=2,
        judged_retrieved_at_k=2,
        relevant_retrieved_at_k=1,
        judgment_coverage_at_k=1.0,
        precision_at_k=0.1,
        recall_at_k=1.0,
        reciprocal_rank_at_k=0.5,
        ndcg_at_k=0.63,
    )
    case = DatasetEvaluationCaseResult(
        case_id=uuid4(),
        query="authentication",
        duration_ms=5.0,
        metrics=metrics,
    )
    return DatasetEvaluationResult(
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        case_count=1,
        total_duration_ms=5.0,
        mean_duration_ms=5.0,
        judgment_coverage_case_count=1,
        mean_judgment_coverage_at_k=1.0,
        mean_precision_at_k=0.1,
        mean_recall_at_k=1.0,
        mrr_at_k=0.5,
        mean_ndcg_at_k=0.63,
        cases=(case,),
    )


def test_persisted_execution_records_only_successful_complete_result() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    executor = FakeExecutor(_result(dataset_id=dataset_id))
    repository = FakeRunRepository()
    service = PersistedDatasetEvaluationService(
        executor=executor,
        runs=EvaluationRunService(repository),
    )

    run = asyncio.run(
        service.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=10,
        )
    )

    assert executor.calls == 1
    assert repository.saved == [run]
    assert run.knowledge_base_id == knowledge_base_id
    assert run.dataset_id == dataset_id
    assert run.cases[0].position == 1
    assert run.cases[0].metrics.cutoff == 10


def test_run_persistence_failure_does_not_return_unpersisted_run() -> None:
    dataset_id = uuid4()
    executor = FakeExecutor(_result(dataset_id=dataset_id))
    repository = FakeRunRepository()
    repository.fail_add = True
    service = PersistedDatasetEvaluationService(
        executor=executor,
        runs=EvaluationRunService(repository),
    )

    with pytest.raises(EvaluationRunPersistenceError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=dataset_id,
                top_k=10,
            )
        )

    assert repository.saved == []


def test_run_detail_is_scoped_by_knowledge_base_and_dataset() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    repository = FakeRunRepository()
    repository.run = EvaluationRun.from_execution(
        knowledge_base_id=knowledge_base_id,
        result=_result(dataset_id=dataset_id),
    )
    service = EvaluationRunService(repository)

    loaded = asyncio.run(
        service.get_by_id(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=repository.run.id,
        )
    )
    assert loaded.id == repository.run.id

    with pytest.raises(EvaluationRunNotFoundError):
        asyncio.run(
            service.get_by_id(
                knowledge_base_id=uuid4(),
                dataset_id=dataset_id,
                run_id=repository.run.id,
            )
        )


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (True, 0), (50, -1), (50, True)],
)
def test_run_history_rejects_invalid_pagination(limit: int, offset: int) -> None:
    service = EvaluationRunService(FakeRunRepository())

    with pytest.raises(EvaluationRunQueryError):
        asyncio.run(
            service.list_by_dataset(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                limit=limit,
                offset=offset,
            )
        )
