"""Validated, backwards-compatible document chunking options."""

from dataclasses import dataclass
from enum import StrEnum

from spurel.documents.chunking import MAX_CHUNK_SIZE_CHARACTERS, DocumentChunkingConfigError

MAX_CHUNK_SIZE_TOKENS = 2_000


class ChunkStrategy(StrEnum):
    CHARACTERS = "characters"
    TOKENS = "tokens"


@dataclass(frozen=True, slots=True)
class DocumentChunkOptions:
    strategy: ChunkStrategy = ChunkStrategy.CHARACTERS
    chunk_size: int = 1_000
    overlap: int = 200

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, ChunkStrategy):
            raise DocumentChunkingConfigError("unsupported chunking strategy")
        ceiling = (
            MAX_CHUNK_SIZE_TOKENS
            if self.strategy == ChunkStrategy.TOKENS
            else MAX_CHUNK_SIZE_CHARACTERS
        )
        if (
            isinstance(self.chunk_size, bool)
            or not isinstance(self.chunk_size, int)
            or not 1 <= self.chunk_size <= ceiling
            or isinstance(self.overlap, bool)
            or not isinstance(self.overlap, int)
            or not 0 <= self.overlap < self.chunk_size
        ):
            raise DocumentChunkingConfigError("invalid chunk size or overlap")
