"""SQLAlchemy persistence models for historical evaluation runs."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_domain import (
    EvaluationRun,
    EvaluationRunCase,
    EvaluationRunSummary,
)
from spurel.retrieval.evaluation import RetrievalMetricValues


class EvaluationRunRecord(Base):
    """Persisted immutable dataset benchmark summary."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_evaluation_runs_mode",
        ),
        CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_evaluation_runs_top_k",
        ),
        CheckConstraint(
            "case_count >= 1 AND case_count <= 100",
            name="ck_evaluation_runs_case_count",
        ),
        CheckConstraint(
            "judgment_coverage_case_count >= 0 "
            "AND judgment_coverage_case_count <= case_count",
            name="ck_evaluation_runs_coverage_case_count",
        ),
        CheckConstraint(
            "total_duration_ms >= 0 AND mean_duration_ms >= 0",
            name="ck_evaluation_runs_duration",
        ),
        CheckConstraint(
            "mean_judgment_coverage_at_k IS NULL "
            "OR (mean_judgment_coverage_at_k >= 0 "
            "AND mean_judgment_coverage_at_k <= 1)",
            name="ck_evaluation_runs_mean_coverage",
        ),
        CheckConstraint(
            "mean_precision_at_k >= 0 AND mean_precision_at_k <= 1 "
            "AND mean_recall_at_k >= 0 AND mean_recall_at_k <= 1 "
            "AND mrr_at_k >= 0 AND mrr_at_k <= 1 "
            "AND mean_ndcg_at_k >= 0 AND mean_ndcg_at_k <= 1",
            name="ck_evaluation_runs_metrics",
        ),
        CheckConstraint(
            """
            (
                mode = 'hybrid'
                AND candidate_k IS NOT NULL
                AND candidate_k >= top_k
                AND candidate_k <= 100
                AND rrf_k IS NOT NULL
                AND rrf_k >= 1
                AND rrf_k <= 1000
            )
            OR
            (
                mode <> 'hybrid'
                AND candidate_k IS NULL
                AND rrf_k IS NULL
            )
            """,
            name="ck_evaluation_runs_hybrid_config",
        ),
        CheckConstraint(
            """
            (
                mode IN ('vector', 'hybrid')
                AND embedding_provider IS NOT NULL
                AND char_length(embedding_provider) > 0
                AND embedding_model IS NOT NULL
                AND char_length(embedding_model) > 0
                AND embedding_dimensions IS NOT NULL
                AND embedding_dimensions > 0
            )
            OR
            (
                mode = 'keyword'
                AND embedding_provider IS NULL
                AND embedding_model IS NULL
                AND embedding_dimensions IS NULL
            )
            """,
            name="ck_evaluation_runs_embedding_config",
        ),
        Index(
            "ix_evaluation_runs_kb_dataset_created_id",
            "knowledge_base_id",
            "dataset_id",
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

    # Historical identifier only. Dataset deletion/editing must not rewrite a run.
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)

    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rrf_k: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding_provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    embedding_dimensions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    mean_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    judgment_coverage_case_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    mean_judgment_coverage_at_k: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    mean_precision_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    mean_recall_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    mrr_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    mean_ndcg_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, run: EvaluationRun) -> "EvaluationRunRecord":
        return cls(
            id=run.id,
            knowledge_base_id=run.knowledge_base_id,
            dataset_id=run.dataset_id,
            mode=run.mode.value,
            top_k=run.top_k,
            candidate_k=run.candidate_k,
            rrf_k=run.rrf_k,
            embedding_provider=run.embedding_provider,
            embedding_model=run.embedding_model,
            embedding_dimensions=run.embedding_dimensions,
            case_count=run.case_count,
            total_duration_ms=run.total_duration_ms,
            mean_duration_ms=run.mean_duration_ms,
            judgment_coverage_case_count=run.judgment_coverage_case_count,
            mean_judgment_coverage_at_k=run.mean_judgment_coverage_at_k,
            mean_precision_at_k=run.mean_precision_at_k,
            mean_recall_at_k=run.mean_recall_at_k,
            mrr_at_k=run.mrr_at_k,
            mean_ndcg_at_k=run.mean_ndcg_at_k,
            created_at=run.created_at,
        )

    def to_summary(self) -> EvaluationRunSummary:
        return EvaluationRunSummary(
            id=self.id,
            knowledge_base_id=self.knowledge_base_id,
            dataset_id=self.dataset_id,
            mode=DatasetEvaluationMode(self.mode),
            top_k=self.top_k,
            candidate_k=self.candidate_k,
            rrf_k=self.rrf_k,
            embedding_provider=self.embedding_provider,
            embedding_model=self.embedding_model,
            embedding_dimensions=self.embedding_dimensions,
            case_count=self.case_count,
            total_duration_ms=self.total_duration_ms,
            mean_duration_ms=self.mean_duration_ms,
            judgment_coverage_case_count=self.judgment_coverage_case_count,
            mean_judgment_coverage_at_k=self.mean_judgment_coverage_at_k,
            mean_precision_at_k=self.mean_precision_at_k,
            mean_recall_at_k=self.mean_recall_at_k,
            mrr_at_k=self.mrr_at_k,
            mean_ndcg_at_k=self.mean_ndcg_at_k,
            created_at=self.created_at,
        )


class EvaluationRunCaseRecord(Base):
    """Persisted per-case metric snapshot for one benchmark run."""

    __tablename__ = "evaluation_run_cases"
    __table_args__ = (
        CheckConstraint(
            "position >= 1 AND position <= 100",
            name="ck_evaluation_run_cases_position",
        ),
        CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_evaluation_run_cases_query",
        ),
        CheckConstraint(
            "duration_ms >= 0",
            name="ck_evaluation_run_cases_duration",
        ),
        CheckConstraint(
            "judged_count >= 1 AND relevant_count >= 1 "
            "AND relevant_count <= judged_count",
            name="ck_evaluation_run_cases_judgments",
        ),
        CheckConstraint(
            "retrieved_count_at_k >= 0 AND retrieved_count_at_k <= 100 "
            "AND judged_retrieved_at_k >= 0 "
            "AND judged_retrieved_at_k <= retrieved_count_at_k "
            "AND relevant_retrieved_at_k >= 0 "
            "AND relevant_retrieved_at_k <= retrieved_count_at_k",
            name="ck_evaluation_run_cases_retrieval_counts",
        ),
        CheckConstraint(
            "judgment_coverage_at_k IS NULL "
            "OR (judgment_coverage_at_k >= 0 AND judgment_coverage_at_k <= 1)",
            name="ck_evaluation_run_cases_coverage",
        ),
        CheckConstraint(
            "precision_at_k >= 0 AND precision_at_k <= 1 "
            "AND recall_at_k >= 0 AND recall_at_k <= 1 "
            "AND reciprocal_rank_at_k >= 0 AND reciprocal_rank_at_k <= 1 "
            "AND ndcg_at_k >= 0 AND ndcg_at_k <= 1",
            name="ck_evaluation_run_cases_metrics",
        ),
        UniqueConstraint(
            "run_id",
            "position",
            name="uq_evaluation_run_cases_run_position",
        ),
        UniqueConstraint(
            "run_id",
            "case_id",
            name="uq_evaluation_run_cases_run_case",
        ),
        Index(
            "ix_evaluation_run_cases_run_position",
            "run_id",
            "position",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Historical identifier only. Dataset case edits/deletion must not rewrite a run.
    case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    judged_count: Mapped[int] = mapped_column(Integer, nullable=False)
    relevant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieved_count_at_k: Mapped[int] = mapped_column(Integer, nullable=False)
    judged_retrieved_at_k: Mapped[int] = mapped_column(Integer, nullable=False)
    relevant_retrieved_at_k: Mapped[int] = mapped_column(Integer, nullable=False)
    judgment_coverage_at_k: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    precision_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    recall_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    reciprocal_rank_at_k: Mapped[float] = mapped_column(Float, nullable=False)
    ndcg_at_k: Mapped[float] = mapped_column(Float, nullable=False)

    @classmethod
    def from_domain(
        cls,
        *,
        run_id: UUID,
        case: EvaluationRunCase,
    ) -> "EvaluationRunCaseRecord":
        metrics = case.metrics
        return cls(
            id=uuid4(),
            run_id=run_id,
            case_id=case.case_id,
            position=case.position,
            query=case.query,
            duration_ms=case.duration_ms,
            judged_count=metrics.judged_count,
            relevant_count=metrics.relevant_count,
            retrieved_count_at_k=metrics.retrieved_count_at_k,
            judged_retrieved_at_k=metrics.judged_retrieved_at_k,
            relevant_retrieved_at_k=metrics.relevant_retrieved_at_k,
            judgment_coverage_at_k=metrics.judgment_coverage_at_k,
            precision_at_k=metrics.precision_at_k,
            recall_at_k=metrics.recall_at_k,
            reciprocal_rank_at_k=metrics.reciprocal_rank_at_k,
            ndcg_at_k=metrics.ndcg_at_k,
        )

    def to_domain(self) -> EvaluationRunCase:
        return EvaluationRunCase(
            position=self.position,
            case_id=self.case_id,
            query=self.query,
            duration_ms=self.duration_ms,
            metrics=RetrievalMetricValues(
                cutoff=0,
                judged_count=self.judged_count,
                relevant_count=self.relevant_count,
                retrieved_count_at_k=self.retrieved_count_at_k,
                judged_retrieved_at_k=self.judged_retrieved_at_k,
                relevant_retrieved_at_k=self.relevant_retrieved_at_k,
                judgment_coverage_at_k=self.judgment_coverage_at_k,
                precision_at_k=self.precision_at_k,
                recall_at_k=self.recall_at_k,
                reciprocal_rank_at_k=self.reciprocal_rank_at_k,
                ndcg_at_k=self.ndcg_at_k,
            ),
        )
