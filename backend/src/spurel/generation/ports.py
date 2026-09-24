"""Provider boundary for text generation."""

from typing import Protocol

from spurel.generation.domain import TextGenerationRequest, TextGenerationResult


class TextGenerationProviderError(RuntimeError):
    """Raised when a text-generation provider request cannot complete."""


class TextGenerationProvider(Protocol):
    """Generate text without exposing provider SDK types to application code."""

    @property
    def provider(self) -> str:
        """Return the stable provider identifier."""
        ...

    @property
    def model(self) -> str:
        """Return the configured model identifier."""
        ...

    async def generate(
        self,
        request: TextGenerationRequest,
    ) -> TextGenerationResult:
        """Generate one validated text response."""
        ...
