"""Document ingestion orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from spurel.documents.domain import DocumentMediaType
from spurel.documents.parsing import (
    DocumentParser,
    ParsedDocument,
    UnsupportedParserMediaTypeError,
)
from spurel.documents.ports import DocumentRepository
from spurel.documents.storage import (
    DocumentBlobStorage,
    DocumentStorageError,
    document_object_key,
)


class DocumentIngestionError(RuntimeError):
    """Base error for document ingestion orchestration."""


class DocumentNotFoundError(DocumentIngestionError):
    """Raised when a scoped document lookup cannot find the document."""


class DocumentContentSizeMismatchError(DocumentIngestionError):
    """Raised when stored content does not match persisted metadata."""


class DocumentContentUnavailableError(DocumentIngestionError):
    """Raised when stored document bytes cannot be loaded."""


@dataclass(frozen=True, slots=True)
class DocumentIngestionResult:
    """Parsed content ready for downstream chunking."""

    document_id: UUID
    knowledge_base_id: UUID
    parsed: ParsedDocument


class DocumentIngestionService:
    """Load, validate, and parse one persisted document."""

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentBlobStorage,
        parsers: Mapping[DocumentMediaType, DocumentParser],
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parsers = dict(parsers)

    async def ingest(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentIngestionResult:
        """Load one scoped document and parse its stored content."""
        document = await self._repository.get_by_id(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        if document is None:
            raise DocumentNotFoundError("document was not found")

        parser = self._parsers.get(document.media_type)
        if parser is None:
            raise UnsupportedParserMediaTypeError(
                "no parser is registered for this media type"
            )

        try:
            content = await self._storage.get(
                object_key=document_object_key(document)
            )
        except DocumentStorageError as exc:
            raise DocumentContentUnavailableError(
                "document content is unavailable"
            ) from exc

        if len(content) != document.size_bytes:
            raise DocumentContentSizeMismatchError(
                "stored content size does not match document metadata"
            )

        parsed = parser.parse(
            content=content,
            media_type=document.media_type,
        )

        return DocumentIngestionResult(
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            parsed=parsed,
        )
