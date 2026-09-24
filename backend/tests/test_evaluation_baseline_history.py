import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselinePromotion,
)
from spurel.evaluation_datasets.baseline_service import EvaluationBaselineService
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
        total_duration_ms=1.0,
        mean_duration_ms=1.0,
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

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        return self.run


class FakeBaselineRepository:
    def __init__(self) -> None:
        self.history: tuple[EvaluationBaselinePromotion, ...] = ()
        self.last_history_call: dict[str, object] | None = None

    async def upsert(self, baseline: EvaluationBaseline) -> EvaluationBaseline:
        return baseline

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaseline]:
        return ()

    async def list_history_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaselinePromotion]:
        self.last_history_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "limit": limit,
            "offset": offset,
        }
        return self.history[offset : offset + limit]

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline | None:
        return None


def test_promotion_snapshot_preserves_baseline_identity_and_configuration() -> None:
    baseline = EvaluationBaseline.from_run(
        run=_run(
            knowledge_base_id=uuid4(),
            dataset_id=uuid4(),
            run_id=uuid4(),
        )
    )

    promotion = EvaluationBaselinePromotion.from_baseline(baseline=baseline)

    assert promotion.baseline_id == baseline.id
    assert promotion.knowledge_base_id == baseline.knowledge_base_id
    assert promotion.dataset_id == baseline.dataset_id
    assert promotion.run_id == baseline.run_id
    assert promotion.configuration == baseline.configuration
    assert (
        promotion.configuration_fingerprint
        == baseline.configuration_fingerprint
    )
    assert promotion.promoted_at == baseline.promoted_at


def test_service_lists_bounded_baseline_promotion_history() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()
    run = _run(
        knowledge_base_id=knowledge_base_id,
        dataset_id=dataset_id,
        run_id=uuid4(),
    )
    baseline = EvaluationBaseline.from_run(run=run)
    promotion = EvaluationBaselinePromotion.from_baseline(baseline=baseline)
    repository = FakeBaselineRepository()
    repository.history = (promotion,)
    service = EvaluationBaselineService(
        repository=repository,
        runs=FakeRunReader(run),
    )

    items = asyncio.run(
        service.list_history_by_dataset(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=25,
            offset=0,
        )
    )

    assert tuple(items) == (promotion,)
    assert repository.last_history_call == {
        "knowledge_base_id": knowledge_base_id,
        "dataset_id": dataset_id,
        "limit": 25,
        "offset": 0,
    }
