"""Provider-neutral text-generation domain values."""

from dataclasses import dataclass

MAX_SYSTEM_PROMPT_LENGTH = 16_000
MAX_USER_PROMPT_LENGTH = 80_000


class TextGenerationResultError(RuntimeError):
    """Raised when a generation request or provider result is invalid."""


@dataclass(frozen=True, slots=True)
class TextGenerationRequest:
    """One bounded text-generation request."""

    system_prompt: str
    user_prompt: str

    def validate(self) -> None:
        """Validate bounded non-empty prompt content."""
        system_prompt = self.system_prompt.strip()
        user_prompt = self.user_prompt.strip()

        if not system_prompt or len(system_prompt) > MAX_SYSTEM_PROMPT_LENGTH:
            raise TextGenerationResultError("system prompt is invalid")
        if not user_prompt or len(user_prompt) > MAX_USER_PROMPT_LENGTH:
            raise TextGenerationResultError("user prompt is invalid")


@dataclass(frozen=True, slots=True)
class TextGenerationResult:
    """Provider-neutral generated text plus provider identity."""

    provider: str
    model: str
    text: str

    def validate(self) -> None:
        """Reject malformed provider output before it reaches the API."""
        if not self.provider.strip():
            raise TextGenerationResultError("generation provider is invalid")
        if not self.model.strip():
            raise TextGenerationResultError("generation model is invalid")
        if not self.text.strip():
            raise TextGenerationResultError("generated text is empty")
