"""SQLAlchemy persistence models for evaluation datasets."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
)
from spurel.retrieval.evaluation import RelevanceJudgment


class EvaluationDatasetRecord(Base):
    """Persisted reusable evaluation dataset."""

    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        CheckConstraint(
            "char_length(name) > 0 AND char_length(name) <= 120",
            name="ck_evaluation_datasets_name",
        ),
        Index(
            "ix_evaluation_datasets_knowledge_base_created_id",
            "knowledge_base_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(
        cls,
        dataset: EvaluationDataset,
    ) -> "EvaluationDatasetRecord":
        return cls(
            id=dataset.id,
            knowledge_base_id=dataset.knowledge_base_id,
            name=dataset.name,
            created_at=dataset.created_at,
        )

    def to_domain(self) -> EvaluationDataset:
        return EvaluationDataset(
            id=self.id,
            knowledge_base_id=self.knowledge_base_id,
            name=self.name,
            created_at=self.created_at,
        )


class EvaluationCaseRecord(Base):
    """Persisted query case belonging to one dataset."""

    __tablename__ = "evaluation_cases"
    __table_args__ = (
        CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_evaluation_cases_query",
        ),
        Index(
            "ix_evaluation_cases_dataset_created_id",
            "dataset_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationJudgmentRecord(Base):
    """Persisted graded relevance label for one evaluation case."""

    __tablename__ = "evaluation_judgments"
    __table_args__ = (
        CheckConstraint(
            "relevance >= 0 AND relevance <= 3",
            name="ck_evaluation_judgments_relevance",
        ),
        UniqueConstraint(
            "case_id",
            "chunk_id",
            name="uq_evaluation_judgments_case_chunk",
        ),
        Index(
            "ix_evaluation_judgments_case_id",
            "case_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Intentionally not a foreign key to live document_chunks.
    # Reprocessing replaces chunk rows; labels must not cascade away.
    chunk_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    relevance: Mapped[int] = mapped_column(Integer, nullable=False)

    @classmethod
    def from_domain(
        cls,
        *,
        case_id: UUID,
        judgment: RelevanceJudgment,
    ) -> "EvaluationJudgmentRecord":
        return cls(
            id=uuid4(),
            case_id=case_id,
            chunk_id=judgment.chunk_id,
            relevance=judgment.relevance,
        )


def case_summary_from_row(
    *,
    record: EvaluationCaseRecord,
    judgment_count: int,
    relevant_judgment_count: int,
) -> EvaluationCaseSummary:
    """Map one case summary query row."""
    return EvaluationCaseSummary(
        id=record.id,
        dataset_id=record.dataset_id,
        query=record.query,
        judgment_count=judgment_count,
        relevant_judgment_count=relevant_judgment_count,
        created_at=record.created_at,
    )


def case_from_records(
    *,
    case_record: EvaluationCaseRecord,
    judgment_records: list[EvaluationJudgmentRecord],
) -> EvaluationCase:
    """Map persisted case rows back to the domain."""
    return EvaluationCase(
        id=case_record.id,
        dataset_id=case_record.dataset_id,
        query=case_record.query,
        judgments=tuple(
            RelevanceJudgment(
                chunk_id=record.chunk_id,
                relevance=record.relevance,
            )
            for record in judgment_records
        ),
        created_at=case_record.created_at,
    )
