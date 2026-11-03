from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from spurel.documents.domain import DocumentMediaType
from spurel.documents.parsing import (
    DocumentExtractedTextLimitError,
    DocumentParseError,
    DocumentPdfEncryptedError,
    DocumentTextContentError,
    UnsupportedParserMediaTypeError,
)
from spurel.infrastructure.parsing.ocr import PdfOcrError, PdfOcrPageLimitError
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



def _pdf_with_text_pages(lines: list[str | None]) -> bytes:
    """Generate a real PDF containing independent plain-text and empty pages."""
    writer = PdfWriter()
    for line in lines:
        page = writer.add_blank_page(width=220, height=220)
        if line is None:
            continue
        font = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(
            b"BT /F1 12 Tf 20 150 Td (" + line.encode("ascii") + b") Tj ET"
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_parser_preserves_actual_page_numbers_and_exact_source_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "false")
    monkeypatch.setenv("SPUREL_PDF_EXTRACTION_MODE", "plain")
    pdf = _pdf_with_text_pages(["Policy on page one", None, "Requirements on page three"])
    parsed = PdfDocumentParser().parse(content=pdf, media_type=DocumentMediaType.PDF)

    assert parsed.text == "Policy on page one\n\nRequirements on page three"
    assert [page.page_number for page in parsed.pages] == [1, 3]
    assert all(not page.used_ocr for page in parsed.pages)
    for page in parsed.pages:
        assert parsed.text[page.start_offset:page.end_offset] in {
            "Policy on page one", "Requirements on page three"
        }
    assert parsed.pages[0].start_offset == 0
    assert parsed.pages[-1].end_offset == len(parsed.text)


def test_pdf_parser_explicit_layout_mode_preserves_page_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "false")
    monkeypatch.setenv("SPUREL_PDF_EXTRACTION_MODE", "layout")
    content = _pdf_with_text_pages(["Column A and B", "Page two"])
    result = PdfDocumentParser().parse(content=content, media_type=DocumentMediaType.PDF)
    assert result.pages[0].page_number == 1
    assert result.pages[1].page_number == 2
    assert "Column A and B" in result.text
    assert "Page two" in result.text


def test_pdf_parser_uses_opt_in_ocr_only_for_textless_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "true")
    monkeypatch.setenv("SPUREL_PDF_OCR_LANGUAGE", "eng")
    monkeypatch.setenv("SPUREL_PDF_OCR_MAX_PAGES", "2")
    scanned: list[int] = []

    def fake_ocr(*, content: bytes, page_number: int, language: str) -> str:
        assert content.startswith(b"%PDF")
        assert language == "eng"
        scanned.append(page_number)
        return "Recovered scan text.\f"

    parsed = PdfDocumentParser(ocr_runner=fake_ocr).parse(
        content=_pdf_with_text_pages(["Normal layer", None, "More normal text"]),
        media_type=DocumentMediaType.PDF,
    )
    assert scanned == [2]
    assert parsed.text == "Normal layer\n\nRecovered scan text.\n\n\nMore normal text"
    assert [(page.page_number, page.used_ocr) for page in parsed.pages] == [
        (1, False), (2, True), (3, False)
    ]
    assert parsed.text[parsed.pages[1].start_offset:parsed.pages[1].end_offset].startswith(
        "Recovered scan text."
    )


def test_pdf_parser_disabled_ocr_never_invokes_external_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "false")
    calls: list[int] = []

    def forbidden_ocr(*, content: bytes, page_number: int, language: str) -> str:
        calls.append(page_number)
        raise AssertionError("OCR must not run when disabled")

    result = PdfDocumentParser(ocr_runner=forbidden_ocr).parse(
        content=_pdf_with_text_pages(["Readable text", None]),
        media_type=DocumentMediaType.PDF,
    )
    assert "Readable text" in result.text
    assert calls == []


def test_pdf_ocr_page_limit_fails_before_persisting_partial_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "true")
    monkeypatch.setenv("SPUREL_PDF_OCR_MAX_PAGES", "1")
    called: list[int] = []

    def fake_ocr(*, content: bytes, page_number: int, language: str) -> str:
        called.append(page_number)
        return "one scan"

    with pytest.raises(PdfOcrPageLimitError):
        PdfDocumentParser(ocr_runner=fake_ocr).parse(
            content=_pdf_with_text_pages([None, None]),
            media_type=DocumentMediaType.PDF,
        )
    assert called == [1]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SPUREL_PDF_OCR_ENABLED", "sometimes"),
        ("SPUREL_PDF_EXTRACTION_MODE", "unknown"),
    ],
)
def test_invalid_pdf_runtime_settings_fail_closed(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises((DocumentParseError, PdfOcrError)):
        PdfDocumentParser().parse(
            content=_pdf_with_text_pages(["One page"]),
            media_type=DocumentMediaType.PDF,
        )


def test_ocr_enabled_rejects_unsafe_language_and_excessive_page_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "true")
    monkeypatch.setenv("SPUREL_PDF_OCR_LANGUAGE", "eng;touch /tmp/pwned")
    with pytest.raises(PdfOcrError):
        PdfDocumentParser().parse(
            content=_pdf_with_text_pages([None]),
            media_type=DocumentMediaType.PDF,
        )
    monkeypatch.setenv("SPUREL_PDF_OCR_LANGUAGE", "eng")
    monkeypatch.setenv("SPUREL_PDF_OCR_MAX_PAGES", "200")
    with pytest.raises(PdfOcrError):
        PdfDocumentParser().parse(
            content=_pdf_with_text_pages([None]),
            media_type=DocumentMediaType.PDF,
        )



def test_pdf_parser_enforces_combined_text_limit_after_local_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_PDF_OCR_ENABLED", "true")
    monkeypatch.setattr("spurel.infrastructure.parsing.pdf.MAX_EXTRACTED_TEXT_CHARACTERS", 5)

    def ocr(*, content: bytes, page_number: int, language: str) -> str:
        return "This OCR content is longer than five characters."

    with pytest.raises(DocumentExtractedTextLimitError):
        PdfDocumentParser(ocr_runner=ocr).parse(
            content=_pdf_with_text_pages([None]),
            media_type=DocumentMediaType.PDF,
        )
