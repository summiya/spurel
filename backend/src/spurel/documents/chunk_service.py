"""Application services for persisted document chunks."""

from collections.abc import Sequence
from uuid import UUID

from spurel.documents.chunk_ports import DocumentChunkRepository
from spurel.documents.chunking import (
    MAX_CHUNKS_PER_DOCUMENT,
    MAX_CHUNK_SIZE_CHARACTERS,
    DocumentChunk,
)


class DocumentChunkSetError(ValueError):
    """Raised when a chunk set violates application invariants."""


class DocumentChunkService:
    """Coordinate chunk persistence through an abstract repository."""

    def __init__(self, repository: DocumentChunkRepository) -> None:
        self._repository = repository

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        """Validate and atomically replace one document's chunk set."""
        _validate_chunk_set(chunks)
        await self._repository.replace_for_document(
            document_id=document_id,
            chunks=chunks,
        )

    async def list_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunk]:
        """List a bounded page of persisted chunks."""
        return await self._repository.list_by_document(
            document_id=document_id,
            limit=limit,
            offset=offset,
        )


def _validate_chunk_set(chunks: Sequence[DocumentChunk]) -> None:
    if not chunks:
        raise DocumentChunkSetError("chunk set must not be empty")

    if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
        raise DocumentChunkSetError("chunk set exceeds the supported count")

    for expected_index, chunk in enumerate(chunks):
        if chunk.index != expected_index:
            raise DocumentChunkSetError(
                "chunk indexes must be contiguous and start at zero"
            )

        if not chunk.text or len(chunk.text) > MAX_CHUNK_SIZE_CHARACTERS:
            raise DocumentChunkSetError("chunk text length is invalid")

        if chunk.start_offset < 0 or chunk.end_offset <= chunk.start_offset:
            raise DocumentChunkSetError("chunk source offsets are invalid")

        if chunk.end_offset - chunk.start_offset > MAX_CHUNK_SIZE_CHARACTERS:
            raise DocumentChunkSetError("chunk source span is too large")
