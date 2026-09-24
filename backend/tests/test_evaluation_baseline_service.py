import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
)
from spurel.evaluation_datasets.baseline_service import (
    EvaluationBaselineNotFoundError,
    EvaluationBaselineQueryError,
    EvaluationBaselineService,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_domain import EvaluationRun


def _run(
    *,
    knowledge_base_id: UUID,
    dataset_id: UUID,
    run_id: UUID,
) -> EvaluationRun:
    return EvaluationRun(
        id=run_id,
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        case_count=1,
        total_duration_ms=2.0,
        mean_duration_ms=2.0,
        judgment_coverage_case_count=1,
        mean_judgment_coverage_at_k=1.0,
        mean_precision_at_k=1.0,
        mean_recall_at_k=1.0,
        mrr_at_k=1.0,
        mean_ndcg_at_k=1.0,
        cases=(),
        created_at=datetime.now(UTC),
    )


class FakeRunReader:
    def __init__(self, run: EvaluationRun) -> None:
        self.run = run
        self.last_call: dict[str, UUID] | None = None

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "run_id": run_id,
        }
        return self.run


class FakeBaselineRepository:
    def __init__(self) -> None:
        self.saved: EvaluationBaseline | None = None
        self.items: tuple[EvaluationBaseline, ...] = ()
        self.resolved: EvaluationBaseline | None = None
        self.last_resolve: EvaluationBaselineConfiguration | None = None

    async def upsert(self, baseline: EvaluationBaseline) -> EvaluationBaseline:
        self.saved = baseline
        return baseline

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaseline]:
        return self.items[offset : offset + limit]

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline | None:
        self.last_resolve = configuration
        return self.resolved


def test_service_promotes_scoped_run_using_its_exact_configuration() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run_id = uuid4()
    run = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=run_id,
    )
    runs = FakeRunReader(run)
    repository = FakeBaselineRepository()
    service = EvaluationBaselineService(repository=repository, runs=runs)

    baseline = asyncio.run(
        service.promote(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
    )

    assert runs.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "run_id": run_id,
    }
    assert repository.saved == baseline
    assert baseline.run_id == run_id
    assert baseline.configuration.mode is DatasetEvaluationMode.KEYWORD
    assert baseline.configuration_fingerprint == baseline.configuration.fingerprint


def test_service_resolves_exact_configuration() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run_id = uuid4()
    baseline = EvaluationBaseline.from_run(
        run=_run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
    )
    repository = FakeBaselineRepository()
    repository.resolved = baseline
    service = EvaluationBaselineService(
        repository=repository,
        runs=FakeRunReader(
            _run(
                knowledge_base_id=knowledge_base_id,
                dataset_id=dataset_id,
                run_id=run_id,
            )
        ),
    )

    resolved = asyncio.run(
        service.resolve(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            configuration=baseline.configuration,
        )
    )

    assert resolved == baseline
    assert repository.last_resolve == baseline.configuration


def test_service_returns_not_found_when_no_config_baseline_exists() -> None:
    run = _run(
        knowledge_base_id=uuid4(),
        dataset_id=uuid4(),
        run_id=uuid4(),
    )
    service = EvaluationBaselineService(
        repository=FakeBaselineRepository(),
        runs=FakeRunReader(run),
    )

    with pytest.raises(EvaluationBaselineNotFoundError):
        asyncio.run(
            service.resolve(
                knowledge_base_id=run.knowledge_base_id,
                dataset_id=run.dataset_id,
                configuration=EvaluationBaselineConfiguration.from_run(run),
            )
        )


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (True, 0), (50, -1), (50, True)],
)
def test_service_rejects_invalid_pagination(limit: int, offset: int) -> None:
    run = _run(
        knowledge_base_id=uuid4(),
        dataset_id=uuid4(),
        run_id=uuid4(),
    )
    service = EvaluationBaselineService(
        repository=FakeBaselineRepository(),
        runs=FakeRunReader(run),
    )

    with pytest.raises(EvaluationBaselineQueryError):
        asyncio.run(
            service.list_by_dataset(
                knowledge_base_id=run.knowledge_base_id,
                dataset_id=run.dataset_id,
                limit=limit,
                offset=offset,
            )
        )
