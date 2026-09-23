"""Runtime configuration for embedding provider wiring."""

import os
from dataclasses import dataclass

from spurel.embeddings.domain import validate_embedding_dimensions


class EmbeddingConfigurationError(RuntimeError):
    """Raised when embedding runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class OpenAIEmbeddingConfig:
    """Environment-backed OpenAI embedding configuration."""

    api_key: str
    model: str
    dimensions: int

    @classmethod
    def from_env(cls) -> "OpenAIEmbeddingConfig":
        """Load and validate OpenAI embedding configuration."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("SPUREL_EMBEDDING_MODEL", "").strip()
        dimensions_raw = os.getenv("SPUREL_EMBEDDING_DIMENSIONS", "").strip()

        if not api_key:
            raise EmbeddingConfigurationError(
                "OpenAI embedding API key is not configured"
            )

        if not model:
            raise EmbeddingConfigurationError(
                "embedding model is not configured"
            )

        try:
            dimensions = int(dimensions_raw)
        except ValueError as exc:
            raise EmbeddingConfigurationError(
                "embedding dimensions are invalid"
            ) from exc

        try:
            validate_embedding_dimensions(dimensions)
        except ValueError as exc:
            raise EmbeddingConfigurationError(
                "embedding dimensions are invalid"
            ) from exc

        return cls(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
        )
