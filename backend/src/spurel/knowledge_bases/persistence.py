"""SQLAlchemy persistence model for knowledge bases."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.knowledge_bases.domain import KnowledgeBase


class KnowledgeBaseRecord(Base):
    """Persisted representation of a knowledge base."""

    __tablename__ = "knowledge_bases"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, knowledge_base: KnowledgeBase) -> "KnowledgeBaseRecord":
        """Create a persistence record from a domain entity."""
        return cls(
            id=knowledge_base.id,
            name=knowledge_base.name,
            created_at=knowledge_base.created_at,
        )

    def to_domain(self) -> KnowledgeBase:
        """Convert the persistence record back to a domain entity."""
        return KnowledgeBase(
            id=self.id,
            name=self.name,
            created_at=self.created_at,
        )
