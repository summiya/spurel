"""Bounded opt-in PDF OCR runner tests; no external OCR program is invoked."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from spurel.infrastructure.parsing.ocr import LocalPdfOcr, PdfOcrError


def test_local_pdf_ocr_uses_fixed_argv_and_cleans_temporary_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, *, capture_output, check, timeout):
        assert capture_output is True
        assert check is False
        assert timeout == 12
        assert isinstance(argv, list)
        calls.append(argv)
        if argv[0] == "pdftoppm":
            assert argv[1:6] == ["-f", "2", "-l", "2", "-singlefile"]
            Path(argv[-1] + ".pgm").write_bytes(b"P5\n1 1\n255\n\xff")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        assert argv[0] == "tesseract"
        assert argv[2:] == ["stdout", "-l", "eng", "--psm", "3"]
        return SimpleNamespace(returncode=0, stdout=b"Scanned words", stderr=b"")

    monkeypatch.setattr("spurel.infrastructure.parsing.ocr.subprocess.run", fake_run)
    assert LocalPdfOcr()(content=b"%PDF-fake", page_number=2, language="eng") == "Scanned words"
    assert len(calls) == 2
    assert not Path(calls[0][-2]).exists()
    assert not Path(calls[1][1]).exists()


def test_local_pdf_ocr_fails_closed_on_unavailable_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):
        raise FileNotFoundError("no OCR binary")

    monkeypatch.setattr("spurel.infrastructure.parsing.ocr.subprocess.run", missing)
    with pytest.raises(PdfOcrError, match="rasterization"):
        LocalPdfOcr()(content=b"PDF", page_number=1, language="eng")


def test_local_pdf_ocr_enforces_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timed_out(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=12)

    monkeypatch.setattr("spurel.infrastructure.parsing.ocr.subprocess.run", timed_out)
    with pytest.raises(PdfOcrError):
        LocalPdfOcr()(content=b"PDF", page_number=1, language="eng")


@pytest.mark.parametrize(
    ("page", "language"),
    [(0, "eng"), (-1, "eng"), (1, "eng;malicious"), (1, "")],
)
def test_local_pdf_ocr_rejects_unsafe_arguments(page: int, language: str) -> None:
    with pytest.raises(PdfOcrError):
        LocalPdfOcr()(content=b"PDF", page_number=page, language=language)
