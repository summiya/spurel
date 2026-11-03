"""Application orchestration from persisted document to persisted chunks."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunking import DocumentChunk, DocumentChunker
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.parsing import ParsedPageSpan


@dataclass(frozen=True, slots=True)
class DocumentChunkPipelineResult:
    """Summary of one successful document chunking run."""

    document_id: UUID
    knowledge_base_id: UUID
    chunk_count: int
    version: int = 1
    attempt_id: UUID | None = None
    reused_active: bool = True


class DocumentChunkPipeline:
    """Parse, chunk, and atomically persist one document's chunk set."""

    def __init__(
        self,
        *,
        ingestion_service: DocumentIngestionService,
        chunker: DocumentChunker,
        chunk_service: DocumentChunkService,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._chunker = chunker
        self._chunk_service = chunk_service

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        chunker: DocumentChunker | None = None,
    ) -> DocumentChunkPipelineResult:
        """Run the document through parse, chunk, and persistence stages."""
        ingestion = await self._ingestion_service.ingest(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

        chunks = _apply_pdf_page_spans(
            (chunker or self._chunker).chunk(text=ingestion.parsed.text),
            ingestion.parsed.pages,
        )

        staging = await self._chunk_service.replace_for_document(
            document_id=ingestion.document_id,
            chunks=chunks,
        )

        return DocumentChunkPipelineResult(
            document_id=ingestion.document_id,
            knowledge_base_id=ingestion.knowledge_base_id,
            chunk_count=len(chunks),
            version=staging.version,
            attempt_id=staging.attempt_id,
            reused_active=staging.reused_active,
        )

    async def promote_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Activate a staged version only after embedding coverage is verified."""
        await self._chunk_service.promote_version(
            document_id=document_id,
            version=version,
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            dimensions=dimensions,
        )

    async def fail_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Fail a staged version without affecting its previous active index."""
        await self._chunk_service.fail_version(
            document_id=document_id, version=version, attempt_id=attempt_id
        )

    async def renew_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Refresh staging ownership before an embedding batch."""
        await self._chunk_service.renew_version(
            document_id=document_id, version=version, attempt_id=attempt_id
        )


def _apply_pdf_page_spans(
    chunks: Sequence[DocumentChunk],
    pages: tuple[ParsedPageSpan, ...],
) -> tuple[DocumentChunk, ...]:
    """Attach page provenance without changing source text or chunk boundaries."""
    if not pages:
        return tuple(chunks)
    annotated: list[DocumentChunk] = []
    for chunk in chunks:
        covered = [
            page
            for page in pages
            if page.start_offset < chunk.end_offset and page.end_offset > chunk.start_offset
        ]
        if not covered:
            annotated.append(chunk)
            continue
        annotated.append(
            replace(
                chunk,
                page_start=min(page.page_number for page in covered),
                page_end=max(page.page_number for page in covered),
                ocr_used=any(page.used_ocr for page in covered),
            )
        )
    return tuple(annotated)
