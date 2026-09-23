"""Document domain."""

from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    Document,
    DocumentFilenameError,
    DocumentMediaType,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)
from spurel.documents.parsing import (
    DocumentParseError,
    DocumentParser,
    DocumentTextContentError,
    DocumentTextEncodingError,
    ParsedDocument,
    UnsupportedParserMediaTypeError,
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
    "DocumentParseError",
    "DocumentParser",
    "DocumentPersistenceError",
    "DocumentRepository",
    "DocumentService",
    "DocumentSizeError",
    "DocumentStorageError",
    "DocumentTextContentError",
    "DocumentTextEncodingError",
    "DocumentUploadCleanupError",
    "DocumentUploadError",
    "DocumentUploadResult",
    "DocumentUploadService",
    "DocumentUploadSizeMismatchError",
    "ParsedDocument",
    "UnsupportedDocumentMediaTypeError",
    "UnsupportedParserMediaTypeError",
]
