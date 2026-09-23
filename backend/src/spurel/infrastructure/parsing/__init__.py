"""Document parsing infrastructure adapters."""

from spurel.infrastructure.parsing.pdf import PdfDocumentParser
from spurel.infrastructure.parsing.text import TextDocumentParser

__all__ = ["PdfDocumentParser", "TextDocumentParser"]
