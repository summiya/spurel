"""Runtime configuration for embedding provider wiring."""

import os
from dataclasses import dataclass

from spurel.embeddings.domain import EmbeddingDimensionError, validate_embedding_dimensions


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
        except EmbeddingDimensionError as exc:
            raise EmbeddingConfigurationError(
                "embedding dimensions are invalid"
            ) from exc

        return cls(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
        )


@dataclass(frozen=True, slots=True)
class EmbeddingProviderConfig:
    """Server-owned provider selection for ingestion, retrieval and evaluation."""

    provider: str
    model: str
    dimensions: int
    api_key: str | None
    base_url: str | None

    @classmethod
    def from_env(cls) -> "EmbeddingProviderConfig":
        from spurel.provider_selection import (
            ProviderSelectionError,
            provider_kind,
            trusted_endpoint,
        )

        try:
            provider = provider_kind("SPUREL_EMBEDDING_PROVIDER")
            if provider == "openai":
                legacy = OpenAIEmbeddingConfig.from_env()
                return cls("openai", legacy.model, legacy.dimensions, legacy.api_key, None)

            model = os.getenv("SPUREL_EMBEDDING_MODEL", "").strip()
            raw_dimensions = os.getenv("SPUREL_EMBEDDING_DIMENSIONS", "").strip()
            if not model or len(model) > 255:
                raise EmbeddingConfigurationError("embedding model is not configured")
            try:
                dimensions = int(raw_dimensions)
                validate_embedding_dimensions(dimensions)
            except (ValueError, EmbeddingDimensionError) as exc:
                raise EmbeddingConfigurationError("embedding dimensions are invalid") from exc

            if provider == "ollama":
                base_url = trusted_endpoint(os.getenv("SPUREL_OLLAMA_BASE_URL", ""), local=True)
                return cls("ollama", model, dimensions, None, base_url)

            base_url = trusted_endpoint(os.getenv("SPUREL_EMBEDDING_BASE_URL", ""))
            key = os.getenv("SPUREL_EMBEDDING_API_KEY", "").strip()
            if not key:
                raise EmbeddingConfigurationError("compatible embedding API key is missing")
            return cls("openai_compatible", model, dimensions, key, base_url)
        except ProviderSelectionError as exc:
            raise EmbeddingConfigurationError(
                "embedding provider configuration is invalid"
            ) from exc
