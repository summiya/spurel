"""SQLAlchemy repository for historical evaluation runs."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary
from spurel.evaluation_datasets.run_persistence import (
    EvaluationRunCaseRecord,
    EvaluationRunRecord,
)
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError


class SqlAlchemyEvaluationRunRepository:
    """Persist and browse immutable evaluation benchmark history."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, run: EvaluationRun) -> None:
        """Persist one run and all case snapshots in one transaction."""
        run_record = EvaluationRunRecord.from_domain(run)
        case_records = [
            EvaluationRunCaseRecord.from_domain(run_id=run.id, case=case)
            for case in run.cases
        ]

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(run_record)
                    session.add_all(case_records)
        except SQLAlchemyError as exc:
            raise EvaluationRunPersistenceError(
                "failed to persist evaluation run"
            ) from exc

    async def list_by_dataset(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[EvaluationRunSummary]:
        """Return newest benchmark summaries without loading per-case rows."""
        statement = (
            select(EvaluationRunRecord)
            .where(
                EvaluationRunRecord.knowledge_base_id == knowledge_base_id,
                EvaluationRunRecord.dataset_id == dataset_id,
            )
            .order_by(
                EvaluationRunRecord.created_at.desc(),
                EvaluationRunRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        try:
            async with self._session_factory() as session:
                records = (await session.execute(statement)).scalars().all()
        except SQLAlchemyError as exc:
            raise EvaluationRunPersistenceError(
                "failed to list evaluation runs"
            ) from exc

        return tuple(record.to_summary() for record in records)

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun | None:
        """Return one scoped run with ordered per-case snapshots."""
        run_statement = select(EvaluationRunRecord).where(
            EvaluationRunRecord.id == run_id,
            EvaluationRunRecord.knowledge_base_id == knowledge_base_id,
            EvaluationRunRecord.dataset_id == dataset_id,
        )
        cases_statement = (
            select(EvaluationRunCaseRecord)
            .where(EvaluationRunCaseRecord.run_id == run_id)
            .order_by(EvaluationRunCaseRecord.position.asc())
        )

        try:
            async with self._session_factory() as session:
                record = (
                    await session.execute(run_statement)
                ).scalar_one_or_none()
                if record is None:
                    return None

                case_records = (
                    await session.execute(cases_statement)
                ).scalars().all()
        except SQLAlchemyError as exc:
            raise EvaluationRunPersistenceError(
                "failed to load evaluation run"
            ) from exc

        if len(case_records) != record.case_count:
            raise EvaluationRunPersistenceError(
                "evaluation run case snapshot is incomplete"
            )

        expected_positions = list(range(1, record.case_count + 1))
        actual_positions = [case_record.position for case_record in case_records]
        if actual_positions != expected_positions:
            raise EvaluationRunPersistenceError(
                "evaluation run case snapshot order is invalid"
            )

        return record.to_domain(
            cases=tuple(
                case_record.to_domain(cutoff=record.top_k)
                for case_record in case_records
            )
        )
