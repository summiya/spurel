"""Shared SQL predicate builder for every retrieval mode.

A search is already knowledge-base scoped by its caller. These predicates
only further narrow that scope; no post-ranking filtering is performed.
"""

from sqlalchemy import Select

from spurel.documents.persistence import DocumentRecord
from spurel.retrieval.metadata_filters import RetrievalMetadataFilters


def apply_document_metadata_filters(
    statement: Select,
    filters: RetrievalMetadataFilters | None,
) -> Select:
    """Apply AND-combined document attributes to one pre-ranking SQL query."""
    if filters is None:
        return statement
    if filters.document_ids:
        statement = statement.where(DocumentRecord.id.in_(filters.document_ids))
    if filters.media_types:
        statement = statement.where(
            DocumentRecord.media_type.in_([item.value for item in filters.media_types])
        )
    if filters.filename_contains is not None:
        # Literal substring search, not an arbitrary user-supplied SQL LIKE pattern.
        escaped = (
            filters.filename_contains.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        statement = statement.where(
            DocumentRecord.filename.ilike(f"%{escaped}%", escape="\\")
        )
    if filters.created_after is not None:
        statement = statement.where(DocumentRecord.created_at >= filters.created_after)
    if filters.created_before is not None:
        statement = statement.where(DocumentRecord.created_at <= filters.created_before)
    return statement
