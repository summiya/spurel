"""Application-facing chunking abstractions for parsed document text."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

MAX_CHUNK_SIZE_CHARACTERS = 20_000
MAX_CHUNKS_PER_DOCUMENT = 10_000


class DocumentChunkingError(ValueError):
    """Raised when document text cannot be chunked safely."""


class DocumentChunkingConfigError(DocumentChunkingError):
    """Raised when chunking configuration is invalid."""


class DocumentChunkLimitError(DocumentChunkingError):
    """Raised when chunking would create too many chunks."""


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """One deterministic slice of normalized source text."""

    index: int
    text: str
    start_offset: int
    end_offset: int


class DocumentChunker(Protocol):
    """Chunking contract used by future ingestion orchestration."""

    def chunk(self, *, text: str) -> Sequence[DocumentChunk]:
        """Split normalized source text into deterministic chunks."""
        ...
