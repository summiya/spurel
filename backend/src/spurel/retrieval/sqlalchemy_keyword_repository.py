"""SQLAlchemy PostgreSQL full-text retrieval adapter."""

from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.persistence import DocumentRecord
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError


class SqlAlchemyKeywordRetrievalRepository:
    """Run PostgreSQL full-text search over one knowledge base."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Return cover-density ranked lexical chunk matches."""
        ts_query = func.websearch_to_tsquery("english", query)
        keyword_score = func.ts_rank_cd(
            DocumentChunkRecord.search_vector,
            ts_query,
            32,
        ).label("keyword_score")

        statement = (
            select(
                DocumentChunkRecord.id,
                DocumentChunkRecord.document_id,
                DocumentChunkRecord.chunk_index,
                DocumentChunkRecord.text,
                DocumentChunkRecord.start_offset,
                DocumentChunkRecord.end_offset,
                keyword_score,
            )
            .join(
                DocumentRecord,
                DocumentRecord.id == DocumentChunkRecord.document_id,
            )
            .where(
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                DocumentChunkRecord.search_vector.op("@@")(ts_query),
            )
            .order_by(
                keyword_score.desc(),
                DocumentChunkRecord.id.asc(),
            )
            .limit(limit)
        )

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise KeywordRetrievalRepositoryError(
                "keyword retrieval failed"
            ) from exc

        return tuple(
            KeywordRetrievalMatch(
                chunk_id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                text=row.text,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                keyword_score=float(row.keyword_score),
            )
            for row in rows
        )
