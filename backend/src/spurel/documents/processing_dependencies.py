"""Dependency wiring for complete document processing."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.documents.chunk_pipeline import DocumentChunkPipeline
from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.domain import DocumentMediaType
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.processing import DocumentProcessingService
from spurel.documents.sqlalchemy_chunk_repository import (
    SqlAlchemyDocumentChunkRepository,
)
from spurel.documents.sqlalchemy_repository import SqlAlchemyDocumentRepository
from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)
from spurel.embeddings.pipeline import DocumentEmbeddingPipeline
from spurel.embeddings.service import ChunkEmbeddingService
from spurel.embeddings.sqlalchemy_repository import (
    SqlAlchemyChunkEmbeddingRepository,
)
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.infrastructure.embeddings import OpenAIEmbeddingProvider
from spurel.infrastructure.parsing.pdf import PdfDocumentParser
from spurel.infrastructure.parsing.text import TextDocumentParser
from spurel.infrastructure.storage import LocalDocumentBlobStorage

LOCAL_STORAGE_ROOT_ENV = "SPUREL_LOCAL_STORAGE_ROOT"
DEFAULT_LOCAL_STORAGE_ROOT = ".spurel/storage"


async def get_document_processing_service() -> AsyncIterator[DocumentProcessingService]:
    """Build and safely dispose the complete document processing service."""
    try:
        config = OpenAIEmbeddingConfig.from_env()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document processing service temporarily unavailable",
        ) from exc

    client = AsyncOpenAI(api_key=config.api_key)

    try:
        document_repository = SqlAlchemyDocumentRepository(async_session_factory)
        chunk_repository = SqlAlchemyDocumentChunkRepository(async_session_factory)
        embedding_repository = SqlAlchemyChunkEmbeddingRepository(
            async_session_factory
        )

        storage_root = Path(
            os.getenv(LOCAL_STORAGE_ROOT_ENV, DEFAULT_LOCAL_STORAGE_ROOT)
        )
        storage = LocalDocumentBlobStorage(storage_root)

        text_parser = TextDocumentParser()
        ingestion_service = DocumentIngestionService(
            repository=document_repository,
            storage=storage,
            parsers={
                DocumentMediaType.TEXT: text_parser,
                DocumentMediaType.MARKDOWN: text_parser,
                DocumentMediaType.PDF: PdfDocumentParser(),
            },
        )

        chunk_pipeline = DocumentChunkPipeline(
            ingestion_service=ingestion_service,
            chunker=FixedSizeDocumentChunker(),
            chunk_service=DocumentChunkService(chunk_repository),
        )

        provider = OpenAIEmbeddingProvider(
            client=client,
            model=config.model,
            dimensions=config.dimensions,
        )
        embedding_pipeline = DocumentEmbeddingPipeline(
            chunk_reader=chunk_repository,
            provider=provider,
            embedding_service=ChunkEmbeddingService(embedding_repository),
        )

        yield DocumentProcessingService(
            chunk_pipeline=chunk_pipeline,
            embedding_pipeline=embedding_pipeline,
        )
    finally:
        await client.close()
