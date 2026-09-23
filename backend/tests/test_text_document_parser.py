import pytest

from spurel.documents.domain import MAX_DOCUMENT_SIZE_BYTES, DocumentMediaType
from spurel.documents.parsing import (
    DocumentParseError,
    DocumentTextContentError,
    DocumentTextEncodingError,
    UnsupportedParserMediaTypeError,
)
from spurel.infrastructure.parsing import TextDocumentParser


@pytest.mark.parametrize(
    "media_type",
    [DocumentMediaType.TEXT, DocumentMediaType.MARKDOWN],
)
def test_parse_supported_text_media_types(media_type: DocumentMediaType) -> None:
    parser = TextDocumentParser()

    result = parser.parse(
        content=b"# Title\r\n\r\nHello\rWorld",
        media_type=media_type,
    )

    assert result.text == "# Title\n\nHello\nWorld"
    assert result.media_type is media_type


def test_parse_strips_utf8_bom() -> None:
    parser = TextDocumentParser()

    result = parser.parse(
        content=b"\xef\xbb\xbfHello",
        media_type=DocumentMediaType.TEXT,
    )

    assert result.text == "Hello"


def test_parse_rejects_pdf_media_type() -> None:
    parser = TextDocumentParser()

    with pytest.raises(UnsupportedParserMediaTypeError):
        parser.parse(
            content=b"%PDF-1.7",
            media_type=DocumentMediaType.PDF,
        )


def test_parse_rejects_invalid_utf8() -> None:
    parser = TextDocumentParser()

    with pytest.raises(DocumentTextEncodingError):
        parser.parse(
            content=b"\xff\xfe\xfd",
            media_type=DocumentMediaType.TEXT,
        )


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"   \n\t  ",
        b"hello\x00world",
        b"hello\x07world",
        b"hello\x7fworld",
    ],
)
def test_parse_rejects_empty_or_control_content(content: bytes) -> None:
    parser = TextDocumentParser()

    with pytest.raises(DocumentTextContentError):
        parser.parse(
            content=content,
            media_type=DocumentMediaType.TEXT,
        )


def test_parse_rejects_content_above_document_size_limit() -> None:
    parser = TextDocumentParser()

    with pytest.raises(DocumentParseError):
        parser.parse(
            content=b"x" * (MAX_DOCUMENT_SIZE_BYTES + 1),
            media_type=DocumentMediaType.TEXT,
        )
