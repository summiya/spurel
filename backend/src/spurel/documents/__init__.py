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
from spurel.documents.storage import DocumentBlobStorage, DocumentStorageError
from spurel.documents.upload_service import (
    DocumentUploadCleanupError,
    DocumentUploadError,
    DocumentUploadResult,
    DocumentUploadService,
    DocumentUploadSizeMismatchError,
)

__all__ = [
    "MAX_DOCUMENT_SIZE_BYTES",
    "Document",
    "DocumentBlobStorage",
    "DocumentFilenameError",
    "DocumentMediaType",
    "DocumentPersistenceError",
    "DocumentRepository",
    "DocumentService",
    "DocumentSizeError",
    "DocumentStorageError",
    "DocumentUploadCleanupError",
    "DocumentUploadError",
    "DocumentUploadResult",
    "DocumentUploadService",
    "DocumentUploadSizeMismatchError",
    "UnsupportedDocumentMediaTypeError",
]
