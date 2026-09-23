"""Provider-independent embedding contracts."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

MAX_EMBEDDING_BATCH_SIZE = 256
MAX_EMBEDDING_DIMENSIONS = 16_384


class EmbeddingError(RuntimeError):
    """Base error for embedding operations."""


class EmbeddingBatchSizeError(EmbeddingError):
    """Raised when an embedding request batch is invalid."""


class EmbeddingDimensionError(EmbeddingError):
    """Raised when an embedding dimension is invalid or inconsistent."""


class EmbeddingResultError(EmbeddingError):
    """Raised when provider results do not match the request contract."""


class EmbeddingProviderError(EmbeddingError):
    """Raised when an embedding provider cannot complete a request."""


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """One immutable validated embedding vector."""

    values: tuple[float, ...]

    @classmethod
    def create(
        cls,
        values: Sequence[float],
        *,
        expected_dimensions: int,
    ) -> "EmbeddingVector":
        """Validate and freeze one provider vector."""
        validate_embedding_dimensions(expected_dimensions)

        if len(values) != expected_dimensions:
            raise EmbeddingDimensionError(
                "embedding vector dimension does not match provider contract"
            )

        normalized: list[float] = []
        for value in values:
            numeric = float(value)
            if not isfinite(numeric):
                raise EmbeddingResultError(
                    "embedding vector contains a non-finite value"
                )
            normalized.append(numeric)

        return cls(values=tuple(normalized))


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    """Validated embeddings aligned with one input batch."""

    vectors: tuple[EmbeddingVector, ...]
    model: str
    dimensions: int

    @classmethod
    def create(
        cls,
        *,
        vectors: Sequence[Sequence[float]],
        input_count: int,
        model: str,
        dimensions: int,
    ) -> "EmbeddingBatch":
        """Validate provider output cardinality and vector dimensions."""
        validate_embedding_dimensions(dimensions)

        if input_count < 1 or input_count > MAX_EMBEDDING_BATCH_SIZE:
            raise EmbeddingBatchSizeError(
                "embedding input count is outside the supported range"
            )

        if len(vectors) != input_count:
            raise EmbeddingResultError(
                "embedding provider returned an unexpected vector count"
            )

        normalized_model = model.strip()
        if not normalized_model:
            raise EmbeddingResultError("embedding model identifier must not be empty")

        return cls(
            vectors=tuple(
                EmbeddingVector.create(
                    vector,
                    expected_dimensions=dimensions,
                )
                for vector in vectors
            ),
            model=normalized_model,
            dimensions=dimensions,
        )


class EmbeddingProvider(Protocol):
    """Provider contract for batched text embeddings."""

    @property
    def provider(self) -> str:
        """Return the stable embedding provider identifier."""
        ...

    @property
    def model(self) -> str:
        """Return the stable provider model identifier."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the vector dimension produced by this provider."""
        ...

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Embed a bounded ordered sequence of texts."""
        ...


def validate_embedding_inputs(texts: Sequence[str]) -> tuple[str, ...]:
    """Validate and freeze an embedding input batch."""
    if not texts or len(texts) > MAX_EMBEDDING_BATCH_SIZE:
        raise EmbeddingBatchSizeError(
            "embedding batch size is outside the supported range"
        )

    normalized: list[str] = []
    for text in texts:
        if not text or not text.strip():
            raise EmbeddingResultError(
                "embedding input text must not be empty"
            )
        normalized.append(text)

    return tuple(normalized)


def validate_embedding_dimensions(dimensions: int) -> None:
    if isinstance(dimensions, bool) or not isinstance(dimensions, int):
        raise EmbeddingDimensionError("embedding dimensions must be an integer")

    if dimensions < 1 or dimensions > MAX_EMBEDDING_DIMENSIONS:
        raise EmbeddingDimensionError(
            "embedding dimensions are outside the supported range"
        )
