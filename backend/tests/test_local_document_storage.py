import asyncio
from collections.abc import AsyncIterable
from pathlib import Path

import pytest

from spurel.documents.storage import DocumentStorageError
from spurel.infrastructure.storage import LocalDocumentBlobStorage


async def _chunks(*values: bytes) -> AsyncIterable[bytes]:
    for value in values:
        yield value


async def _failing_chunks() -> AsyncIterable[bytes]:
    yield b"partial"
    raise RuntimeError("stream failed")


def test_put_streams_object_below_storage_root(tmp_path: Path) -> None:
    storage = LocalDocumentBlobStorage(tmp_path)
    object_key = "knowledge-bases/kb/documents/doc"

    asyncio.run(
        storage.put(
            object_key=object_key,
            chunks=_chunks(b"hello ", b"world"),
        )
    )

    destination = tmp_path / "knowledge-bases" / "kb" / "documents" / "doc"
    assert destination.read_bytes() == b"hello world"
    assert list(destination.parent.glob(".*.tmp")) == []


def test_put_is_atomic_when_stream_fails(tmp_path: Path) -> None:
    storage = LocalDocumentBlobStorage(tmp_path)
    object_key = "knowledge-bases/kb/documents/doc"

    with pytest.raises(RuntimeError, match="stream failed"):
        asyncio.run(
            storage.put(
                object_key=object_key,
                chunks=_failing_chunks(),
            )
        )

    destination = tmp_path / "knowledge-bases" / "kb" / "documents" / "doc"
    assert not destination.exists()
    assert list((tmp_path / "knowledge-bases" / "kb" / "documents").glob(".*.tmp")) == []


@pytest.mark.parametrize(
    "object_key",
    [
        "",
        "/absolute/path",
        "../escape",
        "knowledge-bases/../escape",
        "knowledge-bases//document",
        r"knowledge-bases\escape",
    ],
)
def test_rejects_unsafe_object_keys(tmp_path: Path, object_key: str) -> None:
    storage = LocalDocumentBlobStorage(tmp_path)

    with pytest.raises(DocumentStorageError):
        asyncio.run(
            storage.put(
                object_key=object_key,
                chunks=_chunks(b"data"),
            )
        )


def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalDocumentBlobStorage(tmp_path)
    object_key = "knowledge-bases/kb/documents/doc"

    asyncio.run(storage.put(object_key=object_key, chunks=_chunks(b"data")))
    asyncio.run(storage.delete(object_key=object_key))
    asyncio.run(storage.delete(object_key=object_key))

    assert not (tmp_path / "knowledge-bases" / "kb" / "documents" / "doc").exists()
