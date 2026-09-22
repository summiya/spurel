import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

from spurel.documents.domain import Document
from spurel.documents.service import DocumentService


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.items: list[Document] = []

    async def add(self, document: Document) -> None:
        self.items.append(document)

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        matches = [
            document
            for document in self.items
            if document.knowledge_base_id == knowledge_base_id
        ]
        return tuple(matches[offset : offset + limit])


def test_register_document_through_service() -> None:
    repository = FakeDocumentRepository()
    service = DocumentService(repository)
    knowledge_base_id = uuid4()

    document = asyncio.run(
        service.register(
            knowledge_base_id=knowledge_base_id,
            filename="  architecture.md  ",
            media_type="text/markdown",
            size_bytes=1024,
        )
    )

    assert document.knowledge_base_id == knowledge_base_id
    assert document.filename == "architecture.md"
    assert repository.items == [document]


def test_list_documents_is_scoped_and_bounded() -> None:
    repository = FakeDocumentRepository()
    first_knowledge_base_id = uuid4()
    second_knowledge_base_id = uuid4()

    first = Document.create(
        knowledge_base_id=first_knowledge_base_id,
        filename="one.txt",
        media_type="text/plain",
        size_bytes=10,
    )
    second = Document.create(
        knowledge_base_id=first_knowledge_base_id,
        filename="two.txt",
        media_type="text/plain",
        size_bytes=20,
    )
    other = Document.create(
        knowledge_base_id=second_knowledge_base_id,
        filename="other.txt",
        media_type="text/plain",
        size_bytes=30,
    )
    repository.items.extend([first, second, other])
    service = DocumentService(repository)

    result = asyncio.run(
        service.list_by_knowledge_base(
            knowledge_base_id=first_knowledge_base_id,
            limit=1,
            offset=1,
        )
    )

    assert tuple(result) == (second,)
