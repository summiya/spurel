"""Model-token-aware chunking with lossless Python-character source offsets.

Uses the exact tokenizer for the configured embedding model, not word/character
heuristics. Text slices are taken from the original normalized source, so UTF-8
multi-byte tokens never corrupt excerpts or persisted character offsets.
"""

from functools import lru_cache

import tiktoken

from spurel.documents.chunk_options import MAX_CHUNK_SIZE_TOKENS
from spurel.documents.chunking import (
    MAX_CHUNK_SIZE_CHARACTERS,
    MAX_CHUNKS_PER_DOCUMENT,
    DocumentChunk,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)


@lru_cache(maxsize=16)
def tokenizer_for_model(model: str) -> tiktoken.Encoding:
    """Resolve a known model encoding without any embedding API request."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError as exc:
        raise DocumentChunkingConfigError(
            "the configured embedding model has no supported tokenizer"
        ) from exc


class TokenAwareDocumentChunker:
    """Bounded token windows with token-based overlap and exact source offsets."""

    def __init__(self, *, model: str, chunk_size: int = 512, overlap: int = 64) -> None:
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or not 1 <= chunk_size <= MAX_CHUNK_SIZE_TOKENS
        ):
            raise DocumentChunkingConfigError("token chunk size is outside the supported range")
        if (
            isinstance(overlap, bool)
            or not isinstance(overlap, int)
            or not 0 <= overlap < chunk_size
        ):
            raise DocumentChunkingConfigError(
                "token overlap must be non-negative and smaller than chunk size"
            )
        if not model or not model.strip():
            raise DocumentChunkingConfigError("embedding model is required for token chunking")

        self._encoding = tokenizer_for_model(model.strip())
        self._size = chunk_size
        self._overlap = overlap

    @property
    def encoding_name(self) -> str:
        return self._encoding.name

    def token_count(self, text: str) -> int:
        """Count exact tokens, treating embedded special-token strings as source data."""
        return len(self._encoding.encode(text, disallowed_special=()))

    def chunk(self, *, text: str) -> tuple[DocumentChunk, ...]:
        """Produce exact original-text spans, each within the token and char limits."""
        if not text or not text.strip():
            raise DocumentChunkingError("document text must not be empty")

        chunks: list[DocumentChunk] = []
        start = 0

        while start < len(text):
            if len(chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                raise DocumentChunkLimitError("document would produce too many chunks")

            end = self._farthest_end(text, start)
            if end == start:
                raise DocumentChunkingError(
                    "a single character exceeds the configured token chunk limit"
                )

            excerpt = text[start:end]
            if excerpt.strip():
                chunks.append(
                    DocumentChunk(
                        index=len(chunks),
                        text=excerpt,
                        start_offset=start,
                        end_offset=end,
                    )
                )

            if end == len(text):
                break

            if self._overlap:
                next_start = self._overlap_start(text, start, end)
                start = next_start if next_start > start else end
            else:
                start = end

        if not chunks:
            raise DocumentChunkingError("document text did not produce any usable chunks")

        return tuple(chunks)

    def _farthest_end(self, text: str, start: int) -> int:
        """Find a character boundary whose exact excerpt fits both safety limits."""
        low = start + 1
        high = min(len(text), start + MAX_CHUNK_SIZE_CHARACTERS)
        best = start
        while low <= high:
            midpoint = (low + high) // 2
            if self.token_count(text[start:midpoint]) <= self._size:
                best = midpoint
                low = midpoint + 1
            else:
                high = midpoint - 1

        return best

    def _overlap_start(self, text: str, start: int, end: int) -> int:
        """Reuse at most the requested token count, always advancing in source text."""
        low = start + 1
        high = end
        chosen = end
        while low <= high:
            midpoint = (low + high) // 2
            if self.token_count(text[midpoint:end]) <= self._overlap:
                chosen = midpoint
                high = midpoint - 1
            else:
                low = midpoint + 1
        return chosen
