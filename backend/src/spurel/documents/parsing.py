"""Application-facing parsing abstractions for document content."""

from dataclasses import dataclass
from typing import Protocol

from spurel.documents.domain import DocumentMediaType


class DocumentParseError(ValueError):
    """Raised when document content cannot be parsed safely."""


class UnsupportedParserMediaTypeError(DocumentParseError):
    """Raised when a parser does not support the requested media type."""


class DocumentTextEncodingError(DocumentParseError):
    """Raised when text content is not valid UTF-8."""


class DocumentTextContentError(DocumentParseError):
    """Raised when text content is empty or contains unsafe control bytes."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Normalized text produced by a document parser."""

    text: str
    media_type: DocumentMediaType


class DocumentParser(Protocol):
    """Parser contract used by future ingestion orchestration."""

    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        """Parse raw document bytes into normalized text."""
        ...
