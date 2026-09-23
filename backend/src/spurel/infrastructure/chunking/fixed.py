"""Deterministic fixed-size character chunker."""

from math import ceil

from spurel.documents.chunking import (
    MAX_CHUNKS_PER_DOCUMENT,
    MAX_CHUNK_SIZE_CHARACTERS,
    DocumentChunk,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)


class FixedSizeDocumentChunker:
    """Split text into fixed-size character windows with optional overlap."""

    def __init__(
        self,
        *,
        chunk_size: int = 1_000,
        overlap: int = 200,
    ) -> None:
        _validate_config(chunk_size=chunk_size, overlap=overlap)
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._step = chunk_size - overlap

    def chunk(self, *, text: str) -> tuple[DocumentChunk, ...]:
        """Return deterministic chunks with exact source offsets."""
        if not text or not text.strip():
            raise DocumentChunkingError("document text must not be empty")

        estimated_count = _chunk_count(
            text_length=len(text),
            chunk_size=self._chunk_size,
            step=self._step,
        )
        if estimated_count > MAX_CHUNKS_PER_DOCUMENT:
            raise DocumentChunkLimitError(
                "document would produce too many chunks"
            )

        chunks: list[DocumentChunk] = []

        for start_offset in range(0, len(text), self._step):
            end_offset = min(start_offset + self._chunk_size, len(text))
            chunk_text = text[start_offset:end_offset]

            if chunk_text.strip():
                chunks.append(
                    DocumentChunk(
                        index=len(chunks),
                        text=chunk_text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                    )
                )

            if end_offset == len(text):
                break

        if not chunks:
            raise DocumentChunkingError(
                "document text did not produce any usable chunks"
            )

        return tuple(chunks)


def _validate_config(*, chunk_size: int, overlap: int) -> None:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise DocumentChunkingConfigError("chunk size must be an integer")

    if chunk_size < 1 or chunk_size > MAX_CHUNK_SIZE_CHARACTERS:
        raise DocumentChunkingConfigError(
            "chunk size is outside the supported range"
        )

    if isinstance(overlap, bool) or not isinstance(overlap, int):
        raise DocumentChunkingConfigError("chunk overlap must be an integer")

    if overlap < 0 or overlap >= chunk_size:
        raise DocumentChunkingConfigError(
            "chunk overlap must be non-negative and smaller than chunk size"
        )


def _chunk_count(
    *,
    text_length: int,
    chunk_size: int,
    step: int,
) -> int:
    if text_length <= chunk_size:
        return 1

    return 1 + ceil((text_length - chunk_size) / step)
