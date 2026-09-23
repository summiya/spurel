"""UTF-8 parser for plain text and Markdown documents."""

from spurel.documents.domain import MAX_DOCUMENT_SIZE_BYTES, DocumentMediaType
from spurel.documents.parsing import (
    DocumentParseError,
    DocumentTextContentError,
    DocumentTextEncodingError,
    ParsedDocument,
    UnsupportedParserMediaTypeError,
)

_SUPPORTED_MEDIA_TYPES = {
    DocumentMediaType.TEXT,
    DocumentMediaType.MARKDOWN,
}


class TextDocumentParser:
    """Parse UTF-8 plain text and Markdown into normalized text."""

    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        """Decode and normalize supported text document content."""
        if media_type not in _SUPPORTED_MEDIA_TYPES:
            raise UnsupportedParserMediaTypeError(
                "text parser does not support this media type"
            )

        if not content:
            raise DocumentTextContentError("document content must not be empty")

        if len(content) > MAX_DOCUMENT_SIZE_BYTES:
            raise DocumentParseError("document content exceeds the supported size")

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentTextEncodingError(
                "document content must be valid UTF-8"
            ) from exc

        normalized = _normalize_text(text)

        if not normalized.strip():
            raise DocumentTextContentError(
                "document content must contain non-whitespace text"
            )

        if _contains_disallowed_control_character(normalized):
            raise DocumentTextContentError(
                "document content contains unsupported control characters"
            )

        return ParsedDocument(
            text=normalized,
            media_type=media_type,
        )


def _normalize_text(text: str) -> str:
    """Normalize line endings while preserving document semantics."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _contains_disallowed_control_character(text: str) -> bool:
    allowed_controls = {"\t", "\n"}

    return any(
        (ord(character) < 32 and character not in allowed_controls)
        or ord(character) == 127
        for character in text
    )
