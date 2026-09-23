from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from spurel.documents.domain import DocumentMediaType
from spurel.documents.parsing import (
    DocumentParseError,
    DocumentPdfEncryptedError,
    DocumentTextContentError,
    UnsupportedParserMediaTypeError,
)
from spurel.infrastructure.parsing.pdf import PdfDocumentParser


def _blank_pdf_bytes(*, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if encrypted:
        writer.encrypt("secret")

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_parser_rejects_non_pdf_media_type() -> None:
    parser = PdfDocumentParser()

    with pytest.raises(UnsupportedParserMediaTypeError):
        parser.parse(
            content=b"hello",
            media_type=DocumentMediaType.TEXT,
        )


def test_pdf_parser_rejects_malformed_pdf() -> None:
    parser = PdfDocumentParser()

    with pytest.raises(DocumentParseError):
        parser.parse(
            content=b"not-a-pdf",
            media_type=DocumentMediaType.PDF,
        )


def test_pdf_parser_rejects_encrypted_pdf() -> None:
    parser = PdfDocumentParser()

    with pytest.raises(DocumentPdfEncryptedError):
        parser.parse(
            content=_blank_pdf_bytes(encrypted=True),
            media_type=DocumentMediaType.PDF,
        )


def test_pdf_parser_rejects_pdf_without_extractable_text() -> None:
    parser = PdfDocumentParser()

    with pytest.raises(DocumentTextContentError):
        parser.parse(
            content=_blank_pdf_bytes(),
            media_type=DocumentMediaType.PDF,
        )


def test_generated_blank_pdf_is_valid_pdf() -> None:
    reader = PdfReader(BytesIO(_blank_pdf_bytes()))

    assert len(reader.pages) == 1
