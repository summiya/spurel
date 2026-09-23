"""PDF text extraction adapter."""

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
    UnsupportedParserMediaTypeError,
)

MAX_PDF_PAGES = 500
MAX_EXTRACTED_TEXT_CHARACTERS = 5_000_000


class PdfDocumentParser:
    """Extract normalized text from unencrypted PDFs."""

    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        """Extract text from a supported PDF document."""
        if media_type is not DocumentMediaType.PDF:
            raise UnsupportedParserMediaTypeError(
                "PDF parser does not support this media type"
            )

        if not content:
            raise DocumentTextContentError("document content must not be empty")

        if len(content) > MAX_DOCUMENT_SIZE_BYTES:
            raise DocumentParseError("document content exceeds the supported size")

        try:
            reader = PdfReader(BytesIO(content), strict=False)
        except (PdfReadError, ValueError, OSError) as exc:
            raise DocumentParseError("PDF could not be read") from exc

        if reader.is_encrypted:
            raise DocumentPdfEncryptedError("encrypted PDFs are not supported")

        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentPdfPageLimitError("PDF exceeds the supported page limit")

        extracted_parts: list[str] = []
        extracted_characters = 0

        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except (PdfReadError, ValueError, TypeError, KeyError) as exc:
                raise DocumentParseError("PDF text extraction failed") from exc

            normalized = page_text.replace("\r\n", "\n").replace("\r", "\n")
            extracted_characters += len(normalized)

            if extracted_characters > MAX_EXTRACTED_TEXT_CHARACTERS:
                raise DocumentExtractedTextLimitError(
                    "PDF extracted text exceeds the supported limit"
                )

            if normalized:
                extracted_parts.append(normalized)

        text = "\n\n".join(extracted_parts).strip()

        if not text:
            raise DocumentTextContentError(
                "PDF does not contain extractable text"
            )

        return ParsedDocument(
            text=text,
            media_type=DocumentMediaType.PDF,
        )
