"""Application-facing projections for persisted document chunks."""

from dataclasses import dataclass
from uuid import UUID

from spurel.documents.chunking import DocumentChunk


@dataclass(frozen=True, slots=True)
class StoredDocumentChunk:
    """A persisted chunk with the stable UUID needed by downstream stages."""

    id: UUID
    document_id: UUID
    chunk: DocumentChunk


@dataclass(frozen=True, slots=True)
class StagedDocumentChunkSet:
    """An existing active set or one exclusively claimed processing attempt."""

    version: int
    attempt_id: UUID | None
    reused_active: bool
