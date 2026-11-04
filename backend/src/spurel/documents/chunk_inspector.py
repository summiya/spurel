"""Application values for inspecting persisted document chunks."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

MAX_CHUNK_INSPECTOR_PAGE_SIZE = 100


class ChunkInspectionPersistenceError(RuntimeError):
    """Raised when persisted chunk inspection cannot complete."""


class ChunkInspectionQueryError(ValueError):
    """Raised when a chunk inspection request is invalid."""


@dataclass(frozen=True, slots=True)
class ChunkInspectionItem:
    """One persisted chunk plus safe indexing metadata."""

    id: UUID
    document_id: UUID
    index: int
    text: str
    start_offset: int
    end_offset: int
    embedding_count: int

    @property
    def has_embeddings(self) -> bool:
        """Return whether at least one embedding space is indexed."""
        return self.embedding_count > 0


class ChunkInspectorRepository(Protocol):
    """Read chunk inspection data within an explicit knowledge-base scope."""

    async def list_by_document(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem]:
        """Return a bounded chunk page ordered by chunk index."""
        ...


class ChunkInspectorService:
    """Coordinate bounded document chunk inspection."""

    def __init__(self, repository: ChunkInspectorRepository) -> None:
        self._repository = repository

    async def list_by_document(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem]:
        """List safe persisted chunk details for one scoped document."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_CHUNK_INSPECTOR_PAGE_SIZE
        ):
            raise ChunkInspectionQueryError(
                "chunk inspector page limit is outside the supported range"
            )

        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ChunkInspectionQueryError(
                "chunk inspector page offset is invalid"
            )

        return await self._repository.list_by_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
