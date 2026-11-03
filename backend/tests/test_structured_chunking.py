"""SP-17 structured chunking: boundaries, invariants and compatibility."""

from itertools import pairwise

import pytest

from spurel.documents.chunk_options import ChunkStrategy, DocumentChunkOptions
from spurel.documents.chunking import (
    MAX_CHUNK_SIZE_CHARACTERS,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)
from spurel.infrastructure.chunking.factory import build_document_chunker
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.infrastructure.chunking.structured import (
    StructuredDocumentChunker,
    _markdown_headings,
)
from spurel.infrastructure.chunking.token_aware import TokenAwareDocumentChunker


@pytest.mark.parametrize(
    "strategy",
    (ChunkStrategy.RECURSIVE, ChunkStrategy.MARKDOWN, ChunkStrategy.SENTENCES),
)
def test_all_strategies_preserve_exact_unicode_offsets_and_cover_all_source(
    strategy: ChunkStrategy,
) -> None:
    text = (
        "# Introduction\n\n"
        "Café ☕ uses clear retrieval. It doesn't strip source bytes.\n\n"
        "## Unicode\n\n"
        "Emoji 👩🏽‍💻 are kept intact whenever a natural boundary is available.\n"
        "Now the next paragraph is here. \n\n"
    ) * 4
    chunker = StructuredDocumentChunker(strategy=strategy, chunk_size=83, overlap=0)
    chunks = chunker.chunk(text=text)

    assert len(chunks) > 4
    assert chunks == chunker.chunk(text=text)
    assert chunks[0].start_offset == 0
    assert chunks[-1].end_offset == len(text)
    assert all(chunk.text == text[chunk.start_offset : chunk.end_offset] for chunk in chunks)
    assert all(chunk.index == index for index, chunk in enumerate(chunks))
    assert all(0 < len(chunk.text) <= 83 for chunk in chunks)
    assert all(first.end_offset == second.start_offset for first, second in pairwise(chunks))
    assert "".join(chunk.text for chunk in chunks) == text


def test_recursive_prefers_paragraph_before_sentence_and_character_cut() -> None:
    prefix = "Alpha explains the concept.\n\n"
    text = prefix + "Beta adds another paragraph. " + "More details follow. " * 4
    chunker = StructuredDocumentChunker(
        strategy=ChunkStrategy.RECURSIVE, chunk_size=len(prefix) + 12, overlap=0
    )
    chunks = chunker.chunk(text=text)

    assert chunks[0].text == prefix
    assert chunks[1].text.startswith("Beta")


def test_markdown_keeps_heading_with_its_following_section_and_ignores_fences() -> None:
    first = "# Features\nThis first section describes them.\n\n"
    middle = "## Deployment\nThe deployment steps are explained here.\n\n"
    last = "## Security\nAccess policies belong to a different heading.\n"
    text = first + middle + last
    headings = _markdown_headings(text)
    assert headings == [0, len(first), len(first + middle)]

    chunker = StructuredDocumentChunker(
        strategy=ChunkStrategy.MARKDOWN, chunk_size=len(first) + 8, overlap=0
    )
    chunks = chunker.chunk(text=text)
    assert chunks[0].text == first
    assert chunks[1].text.startswith("## Deployment")

    fenced = (
        "# Intro\n\x60\x60\x60python\n"
        "# Not a heading\n\x60\x60\x60\n"
        "~~~\n## Also code\n~~~\n"
        "## Real\nBody."
    )
    assert _markdown_headings(fenced) == [0, fenced.index("## Real")]


def test_heading_boundary_does_not_carry_overlap_into_the_next_section() -> None:
    first = "# Heading\n" + "First topic with its own meaning.\n\n"
    second = "## Other\n" + "Second topic shouldn't inherit chunks from the first.\n" * 3
    text = first + second
    chunks = StructuredDocumentChunker(
        strategy=ChunkStrategy.MARKDOWN, chunk_size=len(first) + 6, overlap=16
    ).chunk(text=text)

    assert chunks[0].end_offset == len(first)
    assert chunks[1].start_offset == len(first)
    assert chunks[1].text.startswith("## Other")


def test_sentence_aware_prefers_whole_sentences_over_arbitrary_positions() -> None:
    text = (
        "First sentence explains the product. "
        "Second sentence is a short one! "
        "Third sentence gives details? "
        "Final sentence closes the note."
    )
    chunks = StructuredDocumentChunker(
        strategy=ChunkStrategy.SENTENCES, chunk_size=74, overlap=0
    ).chunk(text=text)

    assert len(chunks) >= 2
    assert "".join(item.text for item in chunks) == text
    assert all(item.text.endswith((". ", "! ", "? ")) for item in chunks[:-1])


def test_sentence_boundaries_do_not_split_common_abbreviations() -> None:
    first = "Dr. Smith explains the policy. "
    text = first + "Everyone follows that guidance. One final sentence closes it."
    chunks = StructuredDocumentChunker(
        strategy=ChunkStrategy.SENTENCES, chunk_size=len(first) + 7, overlap=0
    ).chunk(text=text)

    assert chunks[0].text == first
    assert chunks[1].text.startswith("Everyone")


def test_oversized_sentence_and_long_word_fall_back_to_safe_windows() -> None:
    long_word = "A" * (MAX_CHUNK_SIZE_CHARACTERS + 50)
    chunks = StructuredDocumentChunker(
        strategy=ChunkStrategy.SENTENCES, chunk_size=2000, overlap=0
    ).chunk(text=long_word)
    assert "".join(chunk.text for chunk in chunks) == long_word
    assert all(len(chunk.text) <= 2000 for chunk in chunks)
    assert len(chunks) > 1


def test_structured_overlap_is_bounded_and_does_not_stall() -> None:
    text = ("A complete statement is stored here. Another useful fact follows. " * 6).strip()
    chunks = StructuredDocumentChunker(
        strategy=ChunkStrategy.SENTENCES, chunk_size=80, overlap=35
    ).chunk(text=text)

    assert len(chunks) >= 3
    for previous, current in pairwise(chunks):
        assert previous.start_offset < current.start_offset <= previous.end_offset
        assert 0 <= previous.end_offset - current.start_offset <= 35
        assert previous.end_offset <= current.end_offset
        assert current.text == text[current.start_offset : current.end_offset]


@pytest.mark.parametrize("strategy", list(ChunkStrategy)[2:])
def test_all_structured_strategies_reject_empty_and_blank_input(strategy: ChunkStrategy) -> None:
    chunker = StructuredDocumentChunker(strategy=strategy)
    with pytest.raises(DocumentChunkingError):
        chunker.chunk(text="  \n  ")


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (20001, 0), (True, 0), (100, True), (100, -1), (100, 100)],
)
def test_structured_chunker_rejects_invalid_config(size: int, overlap: int) -> None:
    with pytest.raises(DocumentChunkingConfigError):
        StructuredDocumentChunker(
            strategy=ChunkStrategy.RECURSIVE, chunk_size=size, overlap=overlap
        )


def test_structured_chunk_cap_handles_pathological_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spurel.infrastructure.chunking.structured as structured_module

    monkeypatch.setattr(structured_module, "MAX_CHUNKS_PER_DOCUMENT", 3)
    with pytest.raises(DocumentChunkLimitError):
        StructuredDocumentChunker(strategy=ChunkStrategy.RECURSIVE, chunk_size=1, overlap=0).chunk(
            text="hello world"
        )


def test_factory_keeps_both_previous_modes_and_adds_three_opt_in_modes() -> None:
    default = DocumentChunkOptions()
    assert isinstance(
        build_document_chunker(options=default, model="unused"),
        FixedSizeDocumentChunker,
    )
    token = DocumentChunkOptions(strategy=ChunkStrategy.TOKENS, chunk_size=512, overlap=64)
    assert isinstance(
        build_document_chunker(options=token, model="text-embedding-3-small"),
        TokenAwareDocumentChunker,
    )
    for mode in (ChunkStrategy.RECURSIVE, ChunkStrategy.MARKDOWN, ChunkStrategy.SENTENCES):
        options = DocumentChunkOptions(strategy=mode, chunk_size=160, overlap=30)
        chunker = build_document_chunker(options=options, model="unused")
        assert isinstance(chunker, StructuredDocumentChunker)
        assert chunker.chunk(text="This is a real source sentence.")[0].text.startswith("This")


def test_strategies_must_be_valid_enum_members_not_unvalidated_strings() -> None:
    with pytest.raises(DocumentChunkingConfigError):
        DocumentChunkOptions(strategy="recursive")  # type: ignore[arg-type]
    with pytest.raises(DocumentChunkingConfigError):
        StructuredDocumentChunker(strategy=ChunkStrategy.CHARACTERS)
