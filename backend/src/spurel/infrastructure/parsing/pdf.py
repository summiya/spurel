"""PDF text extraction with source page provenance and opt-in local OCR."""

import os
from collections.abc import Callable
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from spurel.documents.domain import MAX_DOCUMENT_SIZE_BYTES, DocumentMediaType
from spurel.documents.parsing import (
    DocumentExtractedTextLimitError,
    DocumentParseError,
    DocumentPdfEncryptedError,
    DocumentPdfPageLimitError,
    DocumentTextContentError,
    ParsedDocument,
    ParsedPageSpan,
    UnsupportedParserMediaTypeError,
)
from spurel.infrastructure.parsing.ocr import (
    LocalPdfOcr,
    PdfOcrConfig,
    PdfOcrPageLimitError,
)

MAX_PDF_PAGES = 500
MAX_EXTRACTED_TEXT_CHARACTERS = 5_000_000

PdfOcrRunner = Callable[..., str]


class PdfDocumentParser:
    """Retain existing text extraction, with optional layout and scanned-page fallback."""

    def __init__(self, *, ocr_runner: PdfOcrRunner | None = None) -> None:
        self._ocr_runner = ocr_runner or LocalPdfOcr()

    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        if media_type is not DocumentMediaType.PDF:
            raise UnsupportedParserMediaTypeError("PDF parser does not support this media type")
        if not content:
            raise DocumentTextContentError("document content must not be empty")
        if len(content) > MAX_DOCUMENT_SIZE_BYTES:
            raise DocumentParseError("document content exceeds the supported size")

        extraction_mode = os.getenv("SPUREL_PDF_EXTRACTION_MODE", "plain").strip().lower()
        if extraction_mode not in {"plain", "layout"}:
            raise DocumentParseError("PDF extraction mode must be plain or layout")
        ocr = PdfOcrConfig.from_env()

        try:
            reader = PdfReader(BytesIO(content), strict=False)
        except (PdfReadError, ValueError, OSError) as exc:
            raise DocumentParseError("PDF could not be read") from exc

        if reader.is_encrypted:
            raise DocumentPdfEncryptedError("encrypted PDFs are not supported")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentPdfPageLimitError("PDF exceeds the supported page limit")

        extracted: list[tuple[int, str, bool]] = []
        extracted_characters = 0
        ocr_attempts = 0

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                if extraction_mode == "layout":
                    page_text = page.extract_text(extraction_mode="layout") or ""
                else:
                    page_text = page.extract_text() or ""
            except (PdfReadError, ValueError, TypeError, KeyError) as exc:
                raise DocumentParseError("PDF text extraction failed") from exc

            normalized = page_text.replace("\r\n", "\n").replace("\r", "\n")
            used_ocr = False

            if not normalized.strip() and ocr.enabled:
                ocr_attempts += 1
                if ocr_attempts > ocr.max_pages:
                    raise PdfOcrPageLimitError("PDF needs OCR on too many pages")
                detected = self._ocr_runner(
                    content=content, page_number=page_number, language=ocr.language
                )
                # Tesseract commonly ends text with a form-feed. Normalize
                # without modifying the source PDF or other extracted pages.
                normalized = (
                    detected.replace("\r\n", "\n")
                    .replace("\r", "\n")
                    .replace("\x0c", "\n")
                )
                used_ocr = bool(normalized.strip())

            extracted_characters += len(normalized)
            if extracted_characters > MAX_EXTRACTED_TEXT_CHARACTERS:
                raise DocumentExtractedTextLimitError(
                    "PDF extracted text exceeds the supported limit"
                )

            if normalized:
                extracted.append((page_number, normalized, used_ocr))

        # Identical to legacy pypdf joining/stripping in plain mode, but
        # retain the character span associated with each numbered PDF page.
        raw_parts: list[str] = []
        pending: list[tuple[int, int, int, bool]] = []
        cursor = 0

        for page_number, part, used_ocr in extracted:
            if raw_parts:
                cursor += 2
            raw_parts.append(part)
            pending.append((page_number, cursor, cursor + len(part), used_ocr))
            cursor += len(part)

        raw_text = "\n\n".join(raw_parts)
        text = raw_text.strip()
        if not text:
            raise DocumentTextContentError("PDF does not contain extractable text")

        leading = len(raw_text) - len(raw_text.lstrip())
        pages = tuple(
            ParsedPageSpan(
                page_number=number,
                start_offset=max(0, start - leading),
                end_offset=min(len(text), end - leading),
                used_ocr=used_ocr,
            )
            for number, start, end, used_ocr in pending
            if min(len(text), end - leading) > max(0, start - leading)
        )

        return ParsedDocument(text=text, media_type=DocumentMediaType.PDF, pages=pages)
