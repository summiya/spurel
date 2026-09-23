"""Dependency wiring for document upload endpoints."""

import os
from pathlib import Path

from spurel.db import async_session_factory
from spurel.documents.sqlalchemy_repository import SqlAlchemyDocumentRepository
from spurel.documents.upload_service import DocumentUploadService
from spurel.infrastructure.storage import LocalDocumentBlobStorage

LOCAL_STORAGE_ROOT_ENV = "SPUREL_LOCAL_STORAGE_ROOT"
DEFAULT_LOCAL_STORAGE_ROOT = ".spurel/storage"


def get_document_upload_service() -> DocumentUploadService:
    """Build the document upload service for local development."""
    repository = SqlAlchemyDocumentRepository(async_session_factory)
    storage_root = Path(os.getenv(LOCAL_STORAGE_ROOT_ENV, DEFAULT_LOCAL_STORAGE_ROOT))
    storage = LocalDocumentBlobStorage(storage_root)
    return DocumentUploadService(repository=repository, storage=storage)
