"""HTTP schemas for documents."""

from datetime import datetime
from typing import Literal
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


class ChunkInspectionResponse(BaseModel):
    """Public persisted chunk inspection data."""

    id: UUID
    document_id: UUID
    index: int
    text: str
    start_offset: int
    end_offset: int
    has_embeddings: bool
    embedding_count: int


class ChunkInspectionListResponse(BaseModel):
    """Bounded page for the Chunk Inspector."""

    items: list[ChunkInspectionResponse]
    limit: int
    offset: int


class DocumentProcessingResponse(BaseModel):
    """Public summary of complete document processing."""

    status: Literal["processed"] = "processed"
    document_id: UUID
    knowledge_base_id: UUID
    chunk_count: int
    embedded_chunk_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
