"""Explicitly enabled, bounded local OCR of otherwise textless PDF pages.

No OCR provider key, remote upload, shell command, or automatic indexing.
The external Poppler/Tesseract programs run only when SPUREL_PDF_OCR_ENABLED=true.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from spurel.documents.parsing import DocumentParseError

MAX_OCR_PAGES = 20
MAX_OCR_IMAGE_BYTES = 20 * 1024 * 1024
MAX_OCR_OUTPUT_BYTES = 2 * 1024 * 1024
OCR_PAGE_TIMEOUT_SECONDS = 12
_ALLOWED_LANGUAGES = re.compile(r"^[a-z]{3}(?:\+[a-z]{3}){0,3}$")


class PdfOcrError(DocumentParseError):
    """OCR could not complete safely or the required local tools are unavailable."""


class PdfOcrPageLimitError(PdfOcrError):
    """The explicitly configured OCR page count was exceeded."""


@dataclass(frozen=True, slots=True)
class PdfOcrConfig:
    enabled: bool = False
    language: str = "eng"
    max_pages: int = 5

    @classmethod
    def from_env(cls) -> "PdfOcrConfig":
        raw = os.getenv("SPUREL_PDF_OCR_ENABLED", "false").strip().lower()
        if raw not in {"true", "false"}:
            raise PdfOcrError("PDF OCR enabled flag must be true or false")
        if raw == "false":
            return cls()

        language = os.getenv("SPUREL_PDF_OCR_LANGUAGE", "eng").strip()
        if not _ALLOWED_LANGUAGES.fullmatch(language):
            raise PdfOcrError("PDF OCR language is invalid")
        try:
            max_pages = int(os.getenv("SPUREL_PDF_OCR_MAX_PAGES", "5"))
        except ValueError as exc:
            raise PdfOcrError("PDF OCR page cap is invalid") from exc
        if not 1 <= max_pages <= MAX_OCR_PAGES:
            raise PdfOcrError("PDF OCR page cap is outside the supported range")
        return cls(enabled=True, language=language, max_pages=max_pages)


class LocalPdfOcr:
    """Render exactly one PDF page and OCR it, within bounded local resources."""

    def __call__(self, *, content: bytes, page_number: int, language: str) -> str:
        if page_number < 1 or not _ALLOWED_LANGUAGES.fullmatch(language):
            raise PdfOcrError("PDF OCR request is invalid")

        # Temporary files are private, never user-controlled names, and removed
        # even on OCR failure. Avoid in-memory unbounded raster output.
        with TemporaryDirectory(prefix="spurel-pdf-ocr-") as temporary:
            root = Path(temporary)
            source = root / "input.pdf"
            raster = root / "page.pgm"
            source.write_bytes(content)

            try:
                rendered = subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page_number),
                        "-l",
                        str(page_number),
                        "-singlefile",
                        "-gray",
                        "-scale-to",
                        "1800",
                        str(source),
                        str(root / "page"),
                    ],
                    capture_output=True,
                    check=False,
                    timeout=OCR_PAGE_TIMEOUT_SECONDS,
                )
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
                raise PdfOcrError("PDF page rasterization is unavailable") from exc

            if rendered.returncode != 0 or not raster.is_file():
                raise PdfOcrError("PDF page rasterization failed")
            if raster.stat().st_size > MAX_OCR_IMAGE_BYTES:
                raise PdfOcrError("PDF page raster image exceeds safety limit")

            try:
                recognized = subprocess.run(
                    ["tesseract", str(raster), "stdout", "-l", language, "--psm", "3"],
                    capture_output=True,
                    check=False,
                    timeout=OCR_PAGE_TIMEOUT_SECONDS,
                )
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
                raise PdfOcrError("local OCR engine is unavailable") from exc

            if recognized.returncode != 0 or len(recognized.stdout) > MAX_OCR_OUTPUT_BYTES:
                raise PdfOcrError("PDF OCR recognition failed or exceeded limits")
            return recognized.stdout.decode("utf-8", errors="replace")
