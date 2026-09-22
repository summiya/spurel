"""Document domain model."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

MAX_DOCUMENT_FILENAME_LENGTH = 255
MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024


class DocumentFilenameError(ValueError):
    """Raised when a document filename is invalid."""


class DocumentSizeError(ValueError):
    """Raised when a document size is outside supported bounds."""


class UnsupportedDocumentMediaTypeError(ValueError):
    """Raised when a document media type is not supported."""


class DocumentMediaType(StrEnum):
    """Media types supported by the first ingestion pipeline."""

    PDF = "application/pdf"
    MARKDOWN = "text/markdown"
    TEXT = "text/plain"

    @classmethod
    def parse(cls, value: str) -> "DocumentMediaType":
        """Parse a media type into the supported domain enum."""
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise UnsupportedDocumentMediaTypeError(
                "document media type is not supported"
            ) from exc


@dataclass(frozen=True, slots=True)
class Document:
    """Metadata for a source document belonging to one knowledge base."""

    id: UUID
    knowledge_base_id: UUID
    filename: str
    media_type: DocumentMediaType
    size_bytes: int
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        knowledge_base_id: UUID,
        filename: str,
        media_type: str,
        size_bytes: int,
    ) -> "Document":
        """Create validated document metadata."""
        normalized_filename = _normalize_filename(filename)
        normalized_media_type = DocumentMediaType.parse(media_type)
        _validate_size(size_bytes)

        return cls(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            filename=normalized_filename,
            media_type=normalized_media_type,
            size_bytes=size_bytes,
            created_at=datetime.now(UTC),
        )


def _normalize_filename(filename: str) -> str:
    normalized = filename.strip()

    if not normalized:
        raise DocumentFilenameError("document filename must not be empty")

    if len(normalized) > MAX_DOCUMENT_FILENAME_LENGTH:
        raise DocumentFilenameError("document filename is too long")

    if "/" in normalized or "\\" in normalized:
        raise DocumentFilenameError("document filename must not contain a path")

    if normalized in {".", ".."}:
        raise DocumentFilenameError("document filename is invalid")

    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise DocumentFilenameError("document filename contains control characters")

    return normalized


def _validate_size(size_bytes: int) -> None:
    if isinstance(size_bytes, bool) or size_bytes <= 0:
        raise DocumentSizeError("document size must be greater than zero")

    if size_bytes > MAX_DOCUMENT_SIZE_BYTES:
        raise DocumentSizeError("document exceeds the maximum supported size")
