"""Runtime configuration for text-generation provider wiring."""

import os
from dataclasses import dataclass

MIN_GENERATION_OUTPUT_TOKENS = 64
MAX_GENERATION_OUTPUT_TOKENS = 4_096


class GenerationConfigurationError(RuntimeError):
    """Raised when generation runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class OpenAIGenerationConfig:
    """Environment-backed OpenAI text-generation configuration."""

    api_key: str
    model: str
    max_output_tokens: int

    @classmethod
    def from_env(cls) -> "OpenAIGenerationConfig":
        """Load and validate OpenAI text-generation configuration."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("SPUREL_GENERATION_MODEL", "").strip()
        max_output_tokens_raw = os.getenv(
            "SPUREL_GENERATION_MAX_OUTPUT_TOKENS",
            "1200",
        ).strip()

        if not api_key:
            raise GenerationConfigurationError(
                "OpenAI generation API key is not configured"
            )
        if not model:
            raise GenerationConfigurationError(
                "generation model is not configured"
            )

        try:
            max_output_tokens = int(max_output_tokens_raw)
        except ValueError as exc:
            raise GenerationConfigurationError(
                "generation max output tokens are invalid"
            ) from exc

        if (
            max_output_tokens < MIN_GENERATION_OUTPUT_TOKENS
            or max_output_tokens > MAX_GENERATION_OUTPUT_TOKENS
        ):
            raise GenerationConfigurationError(
                "generation max output tokens are outside the supported range"
            )

        return cls(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
        )


@dataclass(frozen=True, slots=True)
class GenerationProviderConfig:
    """Server-owned provider selection for RAG and opt-in citation checking."""

    provider: str
    model: str
    max_output_tokens: int
    api_key: str | None
    base_url: str | None

    @classmethod
    def from_env(cls) -> "GenerationProviderConfig":
        from spurel.provider_selection import (
            ProviderSelectionError,
            provider_kind,
            trusted_endpoint,
        )

        try:
            provider = provider_kind("SPUREL_GENERATION_PROVIDER")
            if provider == "openai":
                legacy = OpenAIGenerationConfig.from_env()
                return cls("openai", legacy.model, legacy.max_output_tokens, legacy.api_key, None)

            model = os.getenv("SPUREL_GENERATION_MODEL", "").strip()
            if not model or len(model) > 255:
                raise GenerationConfigurationError("generation model is not configured")
            raw_tokens = os.getenv("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "1200").strip()
            try:
                max_tokens = int(raw_tokens)
            except ValueError as exc:
                raise GenerationConfigurationError("generation output tokens are invalid") from exc
            if not MIN_GENERATION_OUTPUT_TOKENS <= max_tokens <= MAX_GENERATION_OUTPUT_TOKENS:
                raise GenerationConfigurationError("generation output tokens are invalid")

            if provider == "ollama":
                base_url = trusted_endpoint(os.getenv("SPUREL_OLLAMA_BASE_URL", ""), local=True)
                return cls("ollama", model, max_tokens, None, base_url)

            base_url = trusted_endpoint(os.getenv("SPUREL_GENERATION_BASE_URL", ""))
            key = os.getenv("SPUREL_GENERATION_API_KEY", "").strip()
            if not key:
                raise GenerationConfigurationError("compatible generation API key is missing")
            return cls("openai_compatible", model, max_tokens, key, base_url)
        except ProviderSelectionError as exc:
            raise GenerationConfigurationError("generation provider configuration is invalid") from exc
