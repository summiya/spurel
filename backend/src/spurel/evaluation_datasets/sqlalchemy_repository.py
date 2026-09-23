"""SQLAlchemy repository adapter for evaluation datasets."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
)
from spurel.evaluation_datasets.persistence import (
    EvaluationCaseRecord,
    EvaluationDatasetRecord,
    EvaluationJudgmentRecord,
    case_from_records,
    case_summary_from_row,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetPersistenceError


class SqlAlchemyEvaluationDatasetRepository:
    """Persist and read evaluation datasets with scoped async sessions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_dataset(self, dataset: EvaluationDataset) -> None:
        """Persist one dataset."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(EvaluationDatasetRecord.from_domain(dataset))
        except SQLAlchemyError as exc:
            raise EvaluationDatasetPersistenceError(
                "failed to persist evaluation dataset"
            ) from exc

    async def list_datasets(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationDatasetSummary]:
        """Return a bounded dataset page with case counts."""
        case_count = (
            select(func.count(EvaluationCaseRecord.id))
            .where(EvaluationCaseRecord.dataset_id == EvaluationDatasetRecord.id)
            .correlate(EvaluationDatasetRecord)
            .scalar_subquery()
            .label("case_count")
        )

        statement = (
            select(EvaluationDatasetRecord, case_count)
            .where(
                EvaluationDatasetRecord.knowledge_base_id == knowledge_base_id
            )
            .order_by(
                EvaluationDatasetRecord.created_at.desc(),
                EvaluationDatasetRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise EvaluationDatasetPersistenceError(
                "failed to list evaluation datasets"
            ) from exc

        return tuple(
            EvaluationDatasetSummary(
                dataset=record.to_domain(),
                case_count=int(count),
            )
            for record, count in rows
        )

    async def add_case(
        self,
        *,
        knowledge_base_id: UUID,
        case: EvaluationCase,
    ) -> bool:
        """Persist one case and all judgments atomically."""
        dataset_statement = select(EvaluationDatasetRecord.id).where(
            EvaluationDatasetRecord.id == case.dataset_id,
            EvaluationDatasetRecord.knowledge_base_id == knowledge_base_id,
        )

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    dataset_id = (
                        await session.execute(dataset_statement)
                    ).scalar_one_or_none()
                    if dataset_id is None:
                        return False

                    session.add(
                        EvaluationCaseRecord(
                            id=case.id,
                            dataset_id=case.dataset_id,
                            query=case.query,
                            created_at=case.created_at,
                        )
                    )
                    session.add_all(
                        [
                            EvaluationJudgmentRecord.from_domain(
                                case_id=case.id,
                                judgment=judgment,
                            )
                            for judgment in case.judgments
                        ]
                    )
        except SQLAlchemyError as exc:
            raise EvaluationDatasetPersistenceError(
                "failed to persist evaluation case"
            ) from exc

        return True

    async def list_cases(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationCaseSummary] | None:
        """Return case summaries without loading judgment rows."""
        dataset_statement = select(EvaluationDatasetRecord.id).where(
            EvaluationDatasetRecord.id == dataset_id,
            EvaluationDatasetRecord.knowledge_base_id == knowledge_base_id,
        )

        judgment_count = (
            select(func.count(EvaluationJudgmentRecord.id))
            .where(
                EvaluationJudgmentRecord.case_id == EvaluationCaseRecord.id
            )
            .correlate(EvaluationCaseRecord)
            .scalar_subquery()
            .label("judgment_count")
        )
        relevant_count = (
            select(func.count(EvaluationJudgmentRecord.id))
            .where(
                EvaluationJudgmentRecord.case_id == EvaluationCaseRecord.id,
                EvaluationJudgmentRecord.relevance > 0,
            )
            .correlate(EvaluationCaseRecord)
            .scalar_subquery()
            .label("relevant_judgment_count")
        )

        case_statement = (
            select(
                EvaluationCaseRecord,
                judgment_count,
                relevant_count,
            )
            .where(EvaluationCaseRecord.dataset_id == dataset_id)
            .order_by(
                EvaluationCaseRecord.created_at.asc(),
                EvaluationCaseRecord.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                exists = (
                    await session.execute(dataset_statement)
                ).scalar_one_or_none()
                if exists is None:
                    return None

                rows = (await session.execute(case_statement)).all()
        except SQLAlchemyError as exc:
            raise EvaluationDatasetPersistenceError(
                "failed to list evaluation cases"
            ) from exc

        return tuple(
            case_summary_from_row(
                record=record,
                judgment_count=int(count),
                relevant_judgment_count=int(relevant),
            )
            for record, count, relevant in rows
        )

    async def get_case(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase | None:
        """Return one scoped case with ordered judgments."""
        case_statement = (
            select(EvaluationCaseRecord)
            .join(
                EvaluationDatasetRecord,
                EvaluationDatasetRecord.id == EvaluationCaseRecord.dataset_id,
            )
            .where(
                EvaluationDatasetRecord.knowledge_base_id == knowledge_base_id,
                EvaluationCaseRecord.dataset_id == dataset_id,
                EvaluationCaseRecord.id == case_id,
            )
        )
        judgment_statement = (
            select(EvaluationJudgmentRecord)
            .where(EvaluationJudgmentRecord.case_id == case_id)
            .order_by(EvaluationJudgmentRecord.chunk_id.asc())
        )

        try:
            async with self._session_factory() as session:
                case_record = (
                    await session.execute(case_statement)
                ).scalar_one_or_none()
                if case_record is None:
                    return None

                judgment_records = list(
                    (
                        await session.execute(judgment_statement)
                    ).scalars().all()
                )
        except SQLAlchemyError as exc:
            raise EvaluationDatasetPersistenceError(
                "failed to load evaluation case"
            ) from exc

        return case_from_records(
            case_record=case_record,
            judgment_records=judgment_records,
        )
