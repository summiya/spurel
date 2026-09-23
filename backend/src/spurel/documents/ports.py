"""Application-facing persistence ports for documents."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.documents.domain import Document


class DocumentPersistenceError(RuntimeError):
    """Raised when document persistence cannot complete."""


class DocumentRepository(Protocol):
    """Persistence contract used by document application services."""

    async def add(self, document: Document) -> None:
        """Persist document metadata."""
        ...

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        """Return one document scoped to its knowledge base."""
        ...

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        """Return a bounded page for one knowledge base."""
        ...
