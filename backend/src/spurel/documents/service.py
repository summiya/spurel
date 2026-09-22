"""Application services for documents."""

from collections.abc import Sequence
from uuid import UUID

from spurel.documents.domain import Document
from spurel.documents.ports import DocumentRepository


class DocumentService:
    """Coordinate document use cases through an abstract repository."""

    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def register(
        self,
        *,
        knowledge_base_id: UUID,
        filename: str,
        media_type: str,
        size_bytes: int,
    ) -> Document:
        """Validate and persist document metadata."""
        document = Document.create(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            media_type=media_type,
            size_bytes=size_bytes,
        )
        await self._repository.add(document)
        return document

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        """List a bounded page of documents for one knowledge base."""
        return await self._repository.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            offset=offset,
        )
