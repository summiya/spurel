"""Structure-aware, deterministic document chunking with exact source offsets.

These are optional character-bounded strategies. They split on source-text
boundaries and never normalize or rewrite persisted excerpts. Sentence and
heading boundaries are preferred where they fit; oversized units fall back
to smaller separators and finally to a hard, bounded character window.
"""

import re
from bisect import bisect_right

from spurel.documents.chunk_options import ChunkStrategy
from spurel.documents.chunking import (
    MAX_CHUNK_SIZE_CHARACTERS,
    MAX_CHUNKS_PER_DOCUMENT,
    DocumentChunk,
    DocumentChunkingConfigError,
    DocumentChunkingError,
    DocumentChunkLimitError,
)

_PARAGRAPH = re.compile(r"\r?\n[ \t]*\r?\n")
_LINE = re.compile(r"\r?\n")
_SENTENCE = re.compile(r"""[.!?]["'’”)\]]*[ \t\r\n]+""")
_SPACE = re.compile(r"[ \t]+")
_NON_SPACE = re.compile(r"\S")
_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+")
_FENCE = re.compile(r"^ {0,3}(?P<mark>(?:\x60{3,}|~{3,}))")
_STRUCTURED_STRATEGIES = frozenset(
    {ChunkStrategy.RECURSIVE, ChunkStrategy.MARKDOWN, ChunkStrategy.SENTENCES}
)

_COMMON_ABBREVIATIONS = frozenset(
    {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "etc", "vs", "fig", "no", "e.g", "i.e"}
)


def _is_abbreviation_period(text: str, position: int) -> bool:
    """Avoid treating common initials/abbreviations as sentence boundaries."""
    if text[position] != ".":
        return False
    prefix = text[max(0, position - 24) : position].rsplit(maxsplit=1)
    if not prefix:
        return False
    term = prefix[-1].strip("([{'\u201c\u2018").lower()
    return term in _COMMON_ABBREVIATIONS or (len(term) == 1 and term.isalpha())


def _markdown_headings(text: str) -> list[int]:
    """Find real Markdown headings, ignoring heading-like text inside code fences."""
    starts: list[int] = []
    offset = 0
    opened: str | None = None

    for line in text.splitlines(keepends=True):
        marker = _FENCE.match(line)
        if marker:
            fence = marker.group("mark")
            if opened is None:
                opened = fence
            elif fence[0] == opened[0] and len(fence) >= len(opened):
                opened = None
        elif opened is None and _HEADING.match(line):
            starts.append(offset)
        offset += len(line)
    return starts


def _last_separator(pattern: re.Pattern[str], text: str, start: int, limit: int) -> int | None:
    """Return the rightmost complete separator in the bounded window."""
    first_text = _NON_SPACE.search(text, start, limit)
    if first_text is None:
        return None
    boundary = None
    for match in pattern.finditer(text, start, limit):
        if pattern is _SENTENCE and _is_abbreviation_period(text, match.start()):
            continue
        if first_text.start() < match.end() <= limit:
            boundary = match.end()
    return boundary


def _first_overlap_separator(
    pattern: re.Pattern[str], text: str, floor: int, end: int
) -> int | None:
    """Overlap only from a real boundary and never more than requested."""
    for match in pattern.finditer(text, floor, end):
        if pattern is _SENTENCE and _is_abbreviation_period(text, match.start()):
            continue
        if floor <= match.end() < end:
            return match.end()
    return None


class StructuredDocumentChunker:
    """Split Markdown sections, complete sentences, or recursively by separators.

    All limits and overlaps use characters. Original Unicode text is preserved;
    source offsets are always Python-character positions. Whitespace may be
    included with preceding chunks, never rewritten.
    """

    def __init__(
        self,
        *,
        strategy: ChunkStrategy,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> None:
        if strategy not in _STRUCTURED_STRATEGIES or not isinstance(strategy, ChunkStrategy):
            raise DocumentChunkingConfigError("unsupported structured chunking strategy")
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or not 1 <= chunk_size <= MAX_CHUNK_SIZE_CHARACTERS
        ):
            raise DocumentChunkingConfigError("chunk size is outside the supported range")
        if (
            isinstance(overlap, bool)
            or not isinstance(overlap, int)
            or not 0 <= overlap < chunk_size
        ):
            raise DocumentChunkingConfigError(
                "chunk overlap must be non-negative and smaller than chunk size"
            )
        self._strategy = strategy
        self._size = chunk_size
        self._overlap = overlap

    def chunk(self, *, text: str) -> tuple[DocumentChunk, ...]:
        if not text or not text.strip():
            raise DocumentChunkingError("document text must not be empty")

        headings = _markdown_headings(text) if self._strategy == ChunkStrategy.MARKDOWN else []
        chunks: list[DocumentChunk] = []
        position = 0
        windows = 0

        while position < len(text):
            windows += 1
            if windows > MAX_CHUNKS_PER_DOCUMENT:
                raise DocumentChunkLimitError("document would produce too many chunks")

            limit = min(len(text), position + self._size)
            end = (
                len(text)
                if limit == len(text)
                else self._preferred_end(text, position, limit, headings)
            )
            if end <= position:
                end = limit

            excerpt = text[position:end]
            if excerpt.strip():
                chunks.append(
                    DocumentChunk(
                        index=len(chunks),
                        text=excerpt,
                        start_offset=position,
                        end_offset=end,
                    )
                )

            if end == len(text):
                break

            # Never carry overlap across Markdown section headers. Overlap for
            # structured modes starts at a logical boundary, or is omitted.
            position = self._next_start(text, position, end, headings)

        if not chunks:
            raise DocumentChunkingError("document text did not produce any usable chunks")
        return tuple(chunks)

    def _preferred_end(self, text: str, start: int, limit: int, headings: list[int]) -> int:
        if headings:
            index = bisect_right(headings, limit) - 1
            if index >= 0:
                heading_start = headings[index]
                if heading_start > start and text[start:heading_start].strip():
                    return heading_start

        if self._strategy == ChunkStrategy.SENTENCES:
            patterns = (_SENTENCE, _PARAGRAPH, _LINE, _SPACE)
        else:
            patterns = (_PARAGRAPH, _SENTENCE, _LINE, _SPACE)

        for pattern in patterns:
            end = _last_separator(pattern, text, start, limit)
            if end is not None:
                return end
        return limit

    def _next_start(self, text: str, start: int, end: int, headings: list[int]) -> int:
        if self._overlap == 0 or (headings and end in headings):
            return end

        floor = max(start + 1, end - self._overlap)
        patterns = (
            (_SENTENCE, _PARAGRAPH, _LINE, _SPACE)
            if self._strategy == ChunkStrategy.SENTENCES
            else (_PARAGRAPH, _SENTENCE, _LINE, _SPACE)
        )
        for pattern in patterns:
            candidate = _first_overlap_separator(pattern, text, floor, end)
            if candidate is not None and candidate > start:
                # Avoid an overlap crossing a Markdown heading.
                if headings and any(floor <= heading < end for heading in headings):
                    return end
                return candidate

        # Cutting through a sentence/word to force overlap would undermine the
        # purpose of structured splitting. Omit overlap when no boundary fits.
        return end
