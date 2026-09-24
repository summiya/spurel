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
