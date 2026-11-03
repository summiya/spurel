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
    active_chunk_version: int = Field(default=0, ge=0)


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
    chunk_version: int = Field(default=1, ge=1)
    reused_active_version: bool = False


class DocumentChunkVersionResponse(BaseModel):
    """One historic chunk-set version of an immutable uploaded document."""

    version: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    created_at: datetime
    is_active: bool
    status: Literal["processing", "ready", "failed"] = "ready"
    attempt_count: int = Field(default=0, ge=0)


class DocumentChunkVersionListResponse(BaseModel):
    """A bounded page of saved document processing versions."""

    items: list[DocumentChunkVersionResponse]
    limit: int
    offset: int


class VersionedChunkInspectionListResponse(ChunkInspectionListResponse):
    """One explicit historical chunk-set inspection page."""

    version: int = Field(ge=1)
