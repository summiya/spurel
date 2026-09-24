"""Provider-neutral text generation boundaries."""

from spurel.generation.config import (
    GenerationConfigurationError,
    OpenAIGenerationConfig,
)
from spurel.generation.domain import (
    TextGenerationRequest,
    TextGenerationResult,
    TextGenerationResultError,
)
from spurel.generation.ports import TextGenerationProvider, TextGenerationProviderError

__all__ = [
    "GenerationConfigurationError",
    "OpenAIGenerationConfig",
    "TextGenerationProvider",
    "TextGenerationProviderError",
    "TextGenerationRequest",
    "TextGenerationResult",
    "TextGenerationResultError",
]
