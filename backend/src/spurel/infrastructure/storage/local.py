"""Local filesystem implementation of document blob storage."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterable
from pathlib import Path, PurePosixPath
from uuid import uuid4

import aiofiles

from spurel.documents.storage import DocumentStorageError


class LocalDocumentBlobStorage:
    """Store document blobs under a configured local root directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    async def put(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        """Atomically stream one object to local storage."""
        destination = self._resolve_object_key(object_key)
        temporary = destination.with_name(
            f".{destination.name}.{uuid4().hex}.tmp"
        )

        try:
            await asyncio.to_thread(
                destination.parent.mkdir,
                parents=True,
                exist_ok=True,
            )

            async with aiofiles.open(temporary, "wb") as handle:
                async for chunk in chunks:
                    if chunk:
                        await handle.write(chunk)

            await asyncio.to_thread(os.replace, temporary, destination)
        except OSError as exc:
            await self._remove_if_exists(temporary)
            raise DocumentStorageError("local blob write failed") from exc
        except BaseException:
            await self._remove_if_exists(temporary)
            raise

    async def get(self, *, object_key: str) -> bytes:
        """Load one object from local storage."""
        destination = self._resolve_object_key(object_key)

        try:
            async with aiofiles.open(destination, "rb") as handle:
                return await handle.read()
        except FileNotFoundError as exc:
            raise DocumentStorageError("local blob not found") from exc
        except OSError as exc:
            raise DocumentStorageError("local blob read failed") from exc

    async def delete(self, *, object_key: str) -> None:
        """Delete an object if present."""
        destination = self._resolve_object_key(object_key)

        try:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
        except OSError as exc:
            raise DocumentStorageError("local blob delete failed") from exc

    def _resolve_object_key(self, object_key: str) -> Path:
        """Resolve a provider-neutral object key below the configured root."""
        if not object_key or "\\" in object_key or "\x00" in object_key:
            raise DocumentStorageError("invalid local blob object key")

        pure_key = PurePosixPath(object_key)
        if pure_key.is_absolute() or any(
            part in {"", ".", ".."} for part in object_key.split("/")
        ):
            raise DocumentStorageError("invalid local blob object key")

        candidate = self._root.joinpath(*pure_key.parts).resolve()

        if not candidate.is_relative_to(self._root):
            raise DocumentStorageError("local blob object key escapes storage root")

        return candidate

    @staticmethod
    async def _remove_if_exists(path: Path) -> None:
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            pass
