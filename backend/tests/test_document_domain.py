from datetime import UTC
from uuid import uuid4

import pytest

from spurel.documents import (
    MAX_DOCUMENT_SIZE_BYTES,
    Document,
    DocumentFilenameError,
    DocumentMediaType,
    DocumentSizeError,
    UnsupportedDocumentMediaTypeError,
)


def test_create_document_metadata() -> None:
    knowledge_base_id = uuid4()

    document = Document.create(
        knowledge_base_id=knowledge_base_id,
        filename="  architecture.md  ",
        media_type="TEXT/MARKDOWN",
        size_bytes=1024,
    )

    assert document.knowledge_base_id == knowledge_base_id
    assert document.filename == "architecture.md"
    assert document.media_type is DocumentMediaType.MARKDOWN
    assert document.size_bytes == 1024
    assert document.created_at.tzinfo is UTC


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
        "../secret.txt",
        "folder/file.txt",
        "folder\\file.txt",
        ".",
        "..",
        "bad\nname.txt",
    ],
)
def test_create_document_rejects_unsafe_filename(filename: str) -> None:
    with pytest.raises(DocumentFilenameError):
        Document.create(
            knowledge_base_id=uuid4(),
            filename=filename,
            media_type="text/plain",
            size_bytes=1,
        )


@pytest.mark.parametrize("size_bytes", [0, -1, True, MAX_DOCUMENT_SIZE_BYTES + 1])
def test_create_document_rejects_invalid_size(size_bytes: int) -> None:
    with pytest.raises(DocumentSizeError):
        Document.create(
            knowledge_base_id=uuid4(),
            filename="notes.txt",
            media_type="text/plain",
            size_bytes=size_bytes,
        )


def test_create_document_rejects_unsupported_media_type() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError):
        Document.create(
            knowledge_base_id=uuid4(),
            filename="archive.zip",
            media_type="application/zip",
            size_bytes=10,
        )
