"""Typed, bounded filters over document metadata already stored by Spurel.

Filtering is applied in SQL before ranking or hybrid fusion. These are not
document-level access controls: the local workbench has one shared operator.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from spurel.documents.domain import DocumentMediaType

MAX_FILTERED_DOCUMENTS = 20
MAX_FILTERED_MEDIA_TYPES = 3
MAX_FILENAME_FILTER_LENGTH = 100


class RetrievalMetadataFilterError(ValueError):
    """Invalid or unsupported retrieval metadata criteria."""


@dataclass(frozen=True, slots=True)
class RetrievalMetadataFilters:
    """An explicit AND between criteria; multiple IDs/types are OR within a field."""

    document_ids: tuple[UUID, ...] = ()
    media_types: tuple[DocumentMediaType, ...] = ()
    filename_contains: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None

    def __post_init__(self) -> None:
        if not any(
            (
                self.document_ids,
                self.media_types,
                self.filename_contains is not None,
                self.created_after is not None,
                self.created_before is not None,
            )
        ):
            raise RetrievalMetadataFilterError("metadata filter cannot be empty")
        if len(self.document_ids) > MAX_FILTERED_DOCUMENTS or len(set(self.document_ids)) != len(
            self.document_ids
        ):
            raise RetrievalMetadataFilterError("document ID filter is invalid")
        if any(not isinstance(value, UUID) for value in self.document_ids):
            raise RetrievalMetadataFilterError("document IDs must be UUIDs")
        if len(self.media_types) > MAX_FILTERED_MEDIA_TYPES or len(set(self.media_types)) != len(
            self.media_types
        ):
            raise RetrievalMetadataFilterError("media-type filter is invalid")
        if any(not isinstance(value, DocumentMediaType) for value in self.media_types):
            raise RetrievalMetadataFilterError("media type is unsupported")
        if self.filename_contains is not None and (
            not isinstance(self.filename_contains, str)
            or not self.filename_contains.strip()
            or len(self.filename_contains.strip()) > MAX_FILENAME_FILTER_LENGTH
            or any(ord(char) < 32 or ord(char) == 127 for char in self.filename_contains)
        ):
            raise RetrievalMetadataFilterError("filename filter is invalid")
        for date in (self.created_after, self.created_before):
            if date is not None and (
                not isinstance(date, datetime) or date.tzinfo is None or date.utcoffset() is None
            ):
                raise RetrievalMetadataFilterError("date filters require timezone offsets")
        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise RetrievalMetadataFilterError("start date must not follow end date")

    def to_snapshot(self) -> dict[str, Any]:
        """JSON-compatible and deterministic metadata for saved trace provenance."""
        result: dict[str, Any] = {}
        if self.document_ids:
            result["document_ids"] = [str(item) for item in self.document_ids]
        if self.media_types:
            result["media_types"] = [value.value for value in self.media_types]
        if self.filename_contains is not None:
            result["filename_contains"] = self.filename_contains.strip()
        if self.created_after is not None:
            result["created_after"] = self.created_after.astimezone(UTC).isoformat()
        if self.created_before is not None:
            result["created_before"] = self.created_before.astimezone(UTC).isoformat()
        return result

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "RetrievalMetadataFilters":
        """Revalidate stored metadata without permitting unknown filter dimensions."""
        if not isinstance(data, dict) or any(
            key
            not in {
                "document_ids",
                "media_types",
                "filename_contains",
                "created_after",
                "created_before",
            }
            for key in data
        ):
            raise RetrievalMetadataFilterError("saved metadata filter is invalid")
        try:
            raw_documents = data.get("document_ids", [])
            raw_media = data.get("media_types", [])
            if not isinstance(raw_documents, list) or not isinstance(raw_media, list):
                raise ValueError("saved filter arrays are malformed")
            return cls(
                document_ids=tuple(UUID(value) for value in raw_documents),
                media_types=tuple(DocumentMediaType(value) for value in raw_media),
                filename_contains=data.get("filename_contains"),
                created_after=(
                    datetime.fromisoformat(data["created_after"])
                    if "created_after" in data
                    else None
                ),
                created_before=(
                    datetime.fromisoformat(data["created_before"])
                    if "created_before" in data
                    else None
                ),
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise RetrievalMetadataFilterError("saved metadata filter is invalid") from exc
