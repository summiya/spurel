"""SP-16 model-token window tests with real tokenizer encoding."""

import pytest

from spurel.documents.chunk_options import (
    ChunkStrategy,
    DocumentChunkOptions,
)
from spurel.documents.chunking import (
    MAX_CHUNK_SIZE_CHARACTERS,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)
from spurel.documents.token_inspection import measured_tokens
from spurel.infrastructure.chunking.factory import build_document_chunker
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.infrastructure.chunking.token_aware import TokenAwareDocumentChunker

MODEL = "text-embedding-3-small"


def test_token_chunking_is_lossless_unicode_and_uses_real_model_token_limits() -> None:
    text = ("A policy says hello 👩🏽‍💻 café \n<S1> a-b c " * 18).strip()
    chunker = TokenAwareDocumentChunker(model=MODEL, chunk_size=32, overlap=5)

    first = chunker.chunk(text=text)
    second = chunker.chunk(text=text)

    assert first == second
    assert len(first) > 2
    assert first[0].start_offset == 0
    assert first[-1].end_offset == len(text)
    assert chunker.encoding_name == "cl100k_base"

    for i, chunk in enumerate(first):
        assert chunk.index == i
        assert chunk.text == text[chunk.start_offset : chunk.end_offset]
        assert len(chunk.text) <= MAX_CHUNK_SIZE_CHARACTERS
        assert 1 <= chunker.token_count(chunk.text) <= 32
        if i:
            previous = first[i - 1]
            assert previous.start_offset < chunk.start_offset <= previous.end_offset
            overlap_text = text[chunk.start_offset : previous.end_offset]
            assert chunker.token_count(overlap_text) <= 5


def test_whole_excerpt_special_token_strings_are_counted_as_literal_text() -> None:
    text = ("<|endoftext|> " + "end " * 50).strip()
    chunker = TokenAwareDocumentChunker(model=MODEL, chunk_size=20, overlap=2)
    chunks = chunker.chunk(text=text)
    assert all(chunker.token_count(chunk.text) <= 20 for chunk in chunks)


def test_token_chunker_can_stay_within_20000_character_persistence_cap() -> None:
    # Repeated characters tokenize efficiently; char caps still protect DB invariants.
    text = "a" * (MAX_CHUNK_SIZE_CHARACTERS + 7_000)
    chunker = TokenAwareDocumentChunker(model=MODEL, chunk_size=2000, overlap=0)
    chunks = chunker.chunk(text=text)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= MAX_CHUNK_SIZE_CHARACTERS for chunk in chunks)
    assert all(chunker.token_count(chunk.text) <= 2000 for chunk in chunks)
    assert chunks[-1].end_offset == len(text)


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (2001, 0), (100, -1), (100, 100), (True, 0), (100, False)],
)
def test_token_chunker_rejects_invalid_settings(size: int, overlap: int) -> None:
    with pytest.raises(DocumentChunkingConfigError):
        TokenAwareDocumentChunker(model=MODEL, chunk_size=size, overlap=overlap)


def test_token_chunker_fails_closed_on_unsupported_model() -> None:
    with pytest.raises(DocumentChunkingConfigError, match="supported tokenizer"):
        TokenAwareDocumentChunker(model="unknown-spurel-embedding-model", chunk_size=24, overlap=4)


@pytest.mark.parametrize("value", ["", "   \n  "])
def test_token_chunker_rejects_empty_text(value: str) -> None:
    with pytest.raises(DocumentChunkingError):
        TokenAwareDocumentChunker(model=MODEL).chunk(text=value)


def test_token_chunk_count_guard_stops_pathological_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spurel.infrastructure.chunking.token_aware as chunk_module

    monkeypatch.setattr(chunk_module, "MAX_CHUNKS_PER_DOCUMENT", 3)
    chunker = TokenAwareDocumentChunker(model=MODEL, chunk_size=2, overlap=1)
    with pytest.raises(DocumentChunkLimitError):
        chunker.chunk(text="hello world " * 400)


def test_opt_in_strategy_preserves_default_character_chunking() -> None:
    normal = DocumentChunkOptions()
    assert normal == DocumentChunkOptions(
        strategy=ChunkStrategy.CHARACTERS, chunk_size=1000, overlap=200
    )
    assert isinstance(build_document_chunker(options=normal, model=MODEL), FixedSizeDocumentChunker)

    tokens = DocumentChunkOptions(strategy=ChunkStrategy.TOKENS, chunk_size=64, overlap=8)
    assert isinstance(
        build_document_chunker(options=tokens, model=MODEL), TokenAwareDocumentChunker
    )
    with pytest.raises(DocumentChunkingConfigError):
        DocumentChunkOptions(strategy=ChunkStrategy.TOKENS, chunk_size=2001)


def test_existing_character_chunker_still_returns_exact_previous_windows() -> None:
    chunks = FixedSizeDocumentChunker(chunk_size=5, overlap=2).chunk(text="abcdefghij")
    assert [(c.text, c.start_offset, c.end_offset) for c in chunks] == [
        ("abcde", 0, 5),
        ("defgh", 3, 8),
        ("ghij", 6, 10),
    ]


def test_inspected_tokens_name_the_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", MODEL)
    text = "A café & a robot 🤖"
    count, encoding = measured_tokens(text)
    assert encoding == "cl100k_base"
    assert count == TokenAwareDocumentChunker(model=MODEL).token_count(text)
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "unknown-spurel-embedding-model")
    assert measured_tokens(text) == (None, None)
