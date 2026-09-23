"""SQLAlchemy persistence models for retrieval traces."""

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
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


class RetrievalTraceRecord(Base):
    """Persisted retrieval run configuration and timing."""

    __tablename__ = "retrieval_traces"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_retrieval_traces_mode",
        ),
        CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_retrieval_traces_query_length",
        ),
        CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_retrieval_traces_top_k",
        ),
        CheckConstraint(
            "duration_ms >= 0",
            name="ck_retrieval_traces_duration",
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
            name="ck_retrieval_traces_hybrid_config",
        ),
        CheckConstraint(
            """
            (
                mode IN ('vector', 'hybrid')
                AND embedding_provider IS NOT NULL
                AND embedding_model IS NOT NULL
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
            name="ck_retrieval_traces_embedding_space",
        ),
        Index(
            "ix_retrieval_traces_knowledge_base_created_id",
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
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_k: Mapped[int | None] = mapped_column(Integer)
    rrf_k: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, trace: RetrievalTrace) -> "RetrievalTraceRecord":
        """Create a persistence record from a retrieval trace."""
        return cls(
            id=trace.id,
            knowledge_base_id=trace.knowledge_base_id,
            mode=trace.mode.value,
            query=trace.query,
            top_k=trace.top_k,
            candidate_k=trace.candidate_k,
            rrf_k=trace.rrf_k,
            duration_ms=trace.duration_ms,
            embedding_provider=trace.embedding_provider,
            embedding_model=trace.embedding_model,
            embedding_dimensions=trace.embedding_dimensions,
            created_at=trace.created_at,
        )


class RetrievalTraceResultRecord(Base):
    """Immutable snapshot of one ranked result from a retrieval trace."""

    __tablename__ = "retrieval_trace_results"
    __table_args__ = (
        CheckConstraint(
            "rank >= 1 AND rank <= 100",
            name="ck_retrieval_trace_results_rank",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_retrieval_trace_results_chunk_index",
        ),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_retrieval_trace_results_offsets",
        ),
        CheckConstraint(
            "char_length(text) > 0",
            name="ck_retrieval_trace_results_text",
        ),
        UniqueConstraint(
            "trace_id",
            "rank",
            name="uq_retrieval_trace_results_trace_rank",
        ),
        UniqueConstraint(
            "trace_id",
            "chunk_id",
            name="uq_retrieval_trace_results_trace_chunk",
        ),
        Index(
            "ix_retrieval_trace_results_trace_rank",
            "trace_id",
            "rank",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    trace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("retrieval_traces.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot identifiers intentionally do not reference live chunk/document rows.
    # Historical traces must survive document reprocessing and chunk replacement.
    chunk_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    document_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    cosine_similarity: Mapped[float | None] = mapped_column(Float)
    keyword_score: Mapped[float | None] = mapped_column(Float)
    rrf_score: Mapped[float | None] = mapped_column(Float)
    vector_rank: Mapped[int | None] = mapped_column(Integer)
    keyword_rank: Mapped[int | None] = mapped_column(Integer)

    @classmethod
    def from_domain(
        cls,
        *,
        trace_id: UUID,
        result: RetrievalTraceResult,
    ) -> "RetrievalTraceResultRecord":
        """Create one persisted result snapshot."""
        return cls(
            id=uuid4(),
            trace_id=trace_id,
            rank=result.rank,
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            chunk_index=result.chunk_index,
            text=result.text,
            start_offset=result.start_offset,
            end_offset=result.end_offset,
            cosine_similarity=result.cosine_similarity,
            keyword_score=result.keyword_score,
            rrf_score=result.rrf_score,
            vector_rank=result.vector_rank,
            keyword_rank=result.keyword_rank,
        )

    def to_domain(self) -> RetrievalTraceResult:
        """Convert a persisted result snapshot to a domain value."""
        return RetrievalTraceResult(
            rank=self.rank,
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            chunk_index=self.chunk_index,
            text=self.text,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            cosine_similarity=self.cosine_similarity,
            keyword_score=self.keyword_score,
            rrf_score=self.rrf_score,
            vector_rank=self.vector_rank,
            keyword_rank=self.keyword_rank,
        )
