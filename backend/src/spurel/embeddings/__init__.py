"""Embedding application abstractions."""

from spurel.embeddings.chunk import ChunkEmbedding, ChunkEmbeddingMetadataError
from spurel.embeddings.domain import (
    MAX_EMBEDDING_BATCH_SIZE,
    EmbeddingBatch,
    EmbeddingBatchSizeError,
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResultError,
    EmbeddingVector,
    validate_embedding_dimensions,
    validate_embedding_inputs,
)

__all__ = [
    "ChunkEmbedding",
    "ChunkEmbeddingMetadataError",
    "MAX_EMBEDDING_BATCH_SIZE",
    "EmbeddingBatch",
    "EmbeddingBatchSizeError",
    "EmbeddingDimensionError",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResultError",
    "EmbeddingVector",
    "validate_embedding_dimensions",
    "validate_embedding_inputs",
]
