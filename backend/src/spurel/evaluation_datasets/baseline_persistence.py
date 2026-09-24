"""SQLAlchemy persistence model for explicit evaluation baselines."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselineConfigurationError,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode


class EvaluationBaselineRecord(Base):
    """One explicitly promoted run per exact retrieval configuration."""

    __tablename__ = "evaluation_baselines"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_evaluation_baselines_mode",
        ),
        CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_evaluation_baselines_top_k",
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
            name="ck_evaluation_baselines_hybrid_config",
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
            name="ck_evaluation_baselines_embedding_config",
        ),
        UniqueConstraint(
            "knowledge_base_id",
            "dataset_id",
            "configuration_fingerprint",
            name="uq_evaluation_baselines_dataset_config",
        ),
        Index(
            "ix_evaluation_baselines_kb_dataset_promoted_id",
            "knowledge_base_id",
            "dataset_id",
            "promoted_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    configuration_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
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
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @classmethod
    def from_domain(
        cls,
        baseline: EvaluationBaseline,
    ) -> "EvaluationBaselineRecord":
        configuration = baseline.configuration
        return cls(
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

    def to_domain(self) -> EvaluationBaseline:
        configuration = EvaluationBaselineConfiguration(
            mode=DatasetEvaluationMode(self.mode),
            top_k=self.top_k,
            candidate_k=self.candidate_k,
            rrf_k=self.rrf_k,
            embedding_provider=self.embedding_provider,
            embedding_model=self.embedding_model,
            embedding_dimensions=self.embedding_dimensions,
        )
        if self.configuration_fingerprint != configuration.fingerprint:
            raise EvaluationBaselineConfigurationError(
                "persisted baseline configuration fingerprint is invalid"
            )

        return EvaluationBaseline(
            id=self.id,
            knowledge_base_id=self.knowledge_base_id,
            dataset_id=self.dataset_id,
            run_id=self.run_id,
            configuration=configuration,
            configuration_fingerprint=self.configuration_fingerprint,
            promoted_at=self.promoted_at,
        )
