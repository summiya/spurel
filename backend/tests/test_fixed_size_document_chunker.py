import pytest

from spurel.documents.chunking import (
    MAX_CHUNKS_PER_DOCUMENT,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)
from spurel.infrastructure.chunking import FixedSizeDocumentChunker


def test_chunk_returns_deterministic_offsets_and_overlap() -> None:
    chunker = FixedSizeDocumentChunker(chunk_size=5, overlap=2)

    chunks = chunker.chunk(text="abcdefghij")

    assert [(chunk.index, chunk.text, chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
        (0, "abcde", 0, 5),
        (1, "defgh", 3, 8),
        (2, "ghij", 6, 10),
    ]
    assert chunks[0].text[-2:] == chunks[1].text[:2]
    assert chunks[1].text[-2:] == chunks[2].text[:2]


def test_chunk_preserves_exact_source_slices() -> None:
    text = "alpha\n\nbeta gamma"
    chunker = FixedSizeDocumentChunker(chunk_size=8, overlap=2)

    chunks = chunker.chunk(text=text)

    for chunk in chunks:
        assert chunk.text == text[chunk.start_offset : chunk.end_offset]


def test_chunk_short_text_returns_one_chunk() -> None:
    chunker = FixedSizeDocumentChunker(chunk_size=100, overlap=20)

    chunks = chunker.chunk(text="hello")

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == "hello"
    assert chunks[0].start_offset == 0
    assert chunks[0].end_offset == 5


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [
        (0, 0),
        (-1, 0),
        (100, -1),
        (100, 100),
        (100, 101),
        (True, 0),
        (100, False),
    ],
)
def test_chunker_rejects_invalid_configuration(
    chunk_size: int,
    overlap: int,
) -> None:
    with pytest.raises(DocumentChunkingConfigError):
        FixedSizeDocumentChunker(
            chunk_size=chunk_size,
            overlap=overlap,
        )


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_chunk_rejects_blank_text(text: str) -> None:
    chunker = FixedSizeDocumentChunker()

    with pytest.raises(DocumentChunkingError):
        chunker.chunk(text=text)


def test_chunk_rejects_pathological_chunk_count() -> None:
    chunker = FixedSizeDocumentChunker(chunk_size=2, overlap=1)
    text = "x" * (MAX_CHUNKS_PER_DOCUMENT + 2)

    with pytest.raises(DocumentChunkLimitError):
        chunker.chunk(text=text)
