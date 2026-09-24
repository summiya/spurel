"""SQLAlchemy repository for explicit evaluation baselines."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselineConfigurationError,
    EvaluationBaselinePromotion,
)
from spurel.evaluation_datasets.baseline_persistence import (
    EvaluationBaselinePromotionRecord,
    EvaluationBaselineRecord,
)
from spurel.evaluation_datasets.baseline_ports import (
    EvaluationBaselinePersistenceError,
)


class SqlAlchemyEvaluationBaselineRepository:
    """Persist and resolve promoted baselines with async PostgreSQL."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert(self, baseline: EvaluationBaseline) -> EvaluationBaseline:
        """Atomically promote a baseline and append its audit snapshot."""
        configuration = baseline.configuration
        statement = (
            insert(EvaluationBaselineRecord)
            .values(
                id=baseline.id,
                knowledge_base_id=baseline.knowledge_base_id,
                dataset_id=baseline.dataset_id,
                run_id=baseline.run_id,
                configuration_fingerprint=baseline.configuration_fingerprint,
                mode=configuration.mode.value,
                top_k=configuration.top_k,
                candidate_k=configuration.candidate_k,
                rrf_k=configuration.rrf_k,
                embedding_provider=configuration.embedding_provider,
                embedding_model=configuration.embedding_model,
                embedding_dimensions=configuration.embedding_dimensions,
                promoted_at=baseline.promoted_at,
            )
            .on_conflict_do_update(
                constraint="uq_evaluation_baselines_dataset_config",
                set_={
                    "run_id": baseline.run_id,
                    "promoted_at": baseline.promoted_at,
                },
            )
            .returning(EvaluationBaselineRecord)
        )

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    record = (await session.execute(statement)).scalar_one()
                    promoted = record.to_domain()
                    session.add(
                        EvaluationBaselinePromotionRecord.from_domain(
                            EvaluationBaselinePromotion.from_baseline(
                                baseline=promoted
                            )
                        )
                    )
                    return promoted
        except (SQLAlchemyError, EvaluationBaselineConfigurationError) as exc:
            raise EvaluationBaselinePersistenceError(
                "failed to promote evaluation baseline"
            ) from exc

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaseline]:
        """Return promoted baselines newest first."""
        statement = (
            select(EvaluationBaselineRecord)
            .where(
                EvaluationBaselineRecord.knowledge_base_id == knowledge_base_id,
                EvaluationBaselineRecord.dataset_id == dataset_id,
            )
            .order_by(
                EvaluationBaselineRecord.promoted_at.desc(),
                EvaluationBaselineRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                records = (await session.execute(statement)).scalars().all()
                return tuple(record.to_domain() for record in records)
        except (SQLAlchemyError, EvaluationBaselineConfigurationError) as exc:
            raise EvaluationBaselinePersistenceError(
                "failed to list evaluation baselines"
            ) from exc

    async def resolve(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        configuration: EvaluationBaselineConfiguration,
    ) -> EvaluationBaseline | None:
        """Resolve one exact promoted retrieval configuration."""
        statement = select(EvaluationBaselineRecord).where(
            EvaluationBaselineRecord.knowledge_base_id == knowledge_base_id,
            EvaluationBaselineRecord.dataset_id == dataset_id,
            EvaluationBaselineRecord.configuration_fingerprint
            == configuration.fingerprint,
        )

        try:
            async with self._session_factory() as session:
                record = (
                    await session.execute(statement)
                ).scalar_one_or_none()
                return record.to_domain() if record is not None else None
        except (SQLAlchemyError, EvaluationBaselineConfigurationError) as exc:
            raise EvaluationBaselinePersistenceError(
                "failed to resolve evaluation baseline"
            ) from exc

    async def list_history_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationBaselinePromotion]:
        """Return append-only promotion history newest first."""
        statement = (
            select(EvaluationBaselinePromotionRecord)
            .where(
                EvaluationBaselinePromotionRecord.knowledge_base_id
                == knowledge_base_id,
                EvaluationBaselinePromotionRecord.dataset_id == dataset_id,
            )
            .order_by(
                EvaluationBaselinePromotionRecord.promoted_at.desc(),
                EvaluationBaselinePromotionRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                records = (await session.execute(statement)).scalars().all()
                return tuple(record.to_domain() for record in records)
        except (SQLAlchemyError, EvaluationBaselineConfigurationError) as exc:
            raise EvaluationBaselinePersistenceError(
                "failed to list evaluation baseline promotion history"
            ) from exc
