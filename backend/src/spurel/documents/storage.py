"""Application-facing blob storage port for document content."""

from collections.abc import AsyncIterable
from typing import Protocol


class DocumentStorageError(RuntimeError):
    """Raised when document blob storage cannot complete an operation."""


class DocumentBlobStorage(Protocol):
    """Blob storage contract used by document upload orchestration."""

    async def put(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        """Store all chunks under a server-generated object key."""
        ...

    async def delete(self, *, object_key: str) -> None:
        """Delete a previously stored object."""
        ...
