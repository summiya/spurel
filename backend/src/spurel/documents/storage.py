"""Application-facing blob storage port for document content."""

from collections.abc import AsyncIterable
from typing import Protocol

from spurel.documents.domain import Document


class DocumentStorageError(RuntimeError):
    """Raised when document blob storage cannot complete an operation."""


class DocumentBlobStorage(Protocol):
    """Blob storage contract used by document application services."""

    async def put(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        """Store all chunks under a server-generated object key."""
        ...

    async def get(self, *, object_key: str) -> bytes:
        """Load one stored object."""
        ...

    async def delete(self, *, object_key: str) -> None:
        """Delete a previously stored object."""
        ...


def document_object_key(document: Document) -> str:
    """Build the canonical opaque storage key for a document."""
    return (
        f"knowledge-bases/{document.knowledge_base_id}/"
        f"documents/{document.id}"
    )
