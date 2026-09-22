"""Document domain."""

from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    Document,
    DocumentFilenameError,
    DocumentMediaType,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)
from spurel.documents.ports import DocumentPersistenceError, DocumentRepository
from spurel.documents.service import DocumentService

__all__ = [
    "MAX_DOCUMENT_SIZE_BYTES",
    "Document",
    "DocumentFilenameError",
    "DocumentMediaType",
    "DocumentPersistenceError",
    "DocumentRepository",
    "DocumentService",
    "DocumentSizeError",
    "UnsupportedDocumentMediaTypeError",
]
