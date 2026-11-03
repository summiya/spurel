"""Construction of processing chunkers from explicit application configuration."""

from spurel.documents.chunk_options import ChunkStrategy, DocumentChunkOptions
from spurel.documents.chunking import DocumentChunker
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.infrastructure.chunking.structured import StructuredDocumentChunker
from spurel.infrastructure.chunking.token_aware import TokenAwareDocumentChunker


def build_document_chunker(*, options: DocumentChunkOptions, model: str) -> DocumentChunker:
    """Preserve existing modes and opt in to structured splitting explicitly."""
    if options.strategy == ChunkStrategy.CHARACTERS:
        return FixedSizeDocumentChunker(
            chunk_size=options.chunk_size,
            overlap=options.overlap,
        )
    if options.strategy == ChunkStrategy.TOKENS:
        return TokenAwareDocumentChunker(
            model=model,
            chunk_size=options.chunk_size,
            overlap=options.overlap,
        )
    return StructuredDocumentChunker(
        strategy=options.strategy,
        chunk_size=options.chunk_size,
        overlap=options.overlap,
    )
