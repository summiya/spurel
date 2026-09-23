"""HTTP schemas for documents."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from spurel.documents.domain import DocumentMediaType


class DocumentResponse(BaseModel):
    """Public persisted document metadata."""

    id: UUID
    knowledge_base_id: UUID
    filename: str
    media_type: DocumentMediaType
    size_bytes: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Bounded page of persisted document metadata."""

    items: list[DocumentResponse]
    limit: int
    offset: int


class DocumentUploadResponse(DocumentResponse):
    """Public response for a successful document upload."""

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
