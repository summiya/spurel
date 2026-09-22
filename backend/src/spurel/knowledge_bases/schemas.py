"""HTTP schemas for knowledge bases."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateKnowledgeBaseRequest(BaseModel):
    """Payload for creating a knowledge base."""

    name: str = Field(min_length=1, max_length=120)


class KnowledgeBaseResponse(BaseModel):
    """Public representation of a knowledge base."""

    id: UUID
    name: str
    created_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    """Bounded page of knowledge bases."""

    items: list[KnowledgeBaseResponse]
    limit: int
    offset: int
