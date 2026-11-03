"""Application contracts for immutable, knowledge-base-scoped chunk-set versions."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from spurel.documents.chunk_inspector import ChunkInspectionItem

MAX_DOCUMENT_VERSION_PAGE_SIZE = 100


class DocumentVersionPersistenceError(RuntimeError):
    """Raised when persisted chunk version history cannot be loaded."""


class DocumentVersionNotFoundError(LookupError):
    """Raised when a version or document is absent from the requested scope."""


class DocumentVersionQueryError(ValueError):
    """Raised when chunk version paging parameters are invalid."""


@dataclass(frozen=True, slots=True)
class DocumentChunkVersion:
    """An immutable indexing snapshot, not a new upload of source document bytes."""

    version: int
    chunk_count: int
    created_at: datetime
    is_active: bool


class DocumentVersionRepository(Protocol):
    """Read historical version metadata and chunks within an explicit KB scope."""

    async def list_versions(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunkVersion] | None:
        """Return one page, or None when the source document is out of scope."""
        ...

    async def list_version_chunks(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        version: int,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem] | None:
        """Return historical chunks, or None for a missing or out-of-scope version."""
        ...


class DocumentVersionService:
    """Validate and coordinate read-only history access."""

    def __init__(self, repository: DocumentVersionRepository) -> None:
        self._repository = repository

    async def list_versions(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunkVersion]:
        """Return the version history of one scoped source document."""
        _validate_page(limit=limit, offset=offset)
        versions = await self._repository.list_versions(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
        if versions is None:
            raise DocumentVersionNotFoundError("document was not found")
        return versions

    async def list_version_chunks(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        version: int,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem]:
        """Inspect one immutable chunk set, including inactive historical sets."""
        _validate_page(limit=limit, offset=offset)
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise DocumentVersionQueryError("chunk version is invalid")
        chunks = await self._repository.list_version_chunks(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            version=version,
            limit=limit,
            offset=offset,
        )
        if chunks is None:
            raise DocumentVersionNotFoundError("document version was not found")
        return chunks


def _validate_page(*, limit: int, offset: int) -> None:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAX_DOCUMENT_VERSION_PAGE_SIZE
    ):
        raise DocumentVersionQueryError("document version page limit is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise DocumentVersionQueryError("document version page offset is invalid")
