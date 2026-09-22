"""Document domain."""

from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    Document,
    DocumentFilenameError,
    DocumentMediaType,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)

__all__ = [
    "MAX_DOCUMENT_SIZE_BYTES",
    "Document",
    "DocumentFilenameError",
    "DocumentMediaType",
    "DocumentSizeError",
    "UnsupportedDocumentMediaTypeError",
]
