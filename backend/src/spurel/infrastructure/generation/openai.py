"""OpenAI implementation of the provider-neutral generation contract."""

from openai import AsyncOpenAI

from spurel.generation.domain import (
    TextGenerationRequest,
    TextGenerationResult,
    TextGenerationResultError,
)
from spurel.generation.ports import TextGenerationProviderError


class OpenAITextGenerationProvider:
    """Generate bounded text responses while hiding OpenAI SDK types."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
        max_output_tokens: int,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise TextGenerationResultError(
                "generation model identifier must not be empty"
            )
        if isinstance(max_output_tokens, bool) or not isinstance(
            max_output_tokens,
            int,
        ):
            raise TextGenerationResultError(
                "generation max output tokens must be an integer"
            )
        if max_output_tokens < 1:
            raise TextGenerationResultError(
                "generation max output tokens must be positive"
            )

        self._client = client
        self._model = normalized_model
        self._max_output_tokens = max_output_tokens

    @property
    def provider(self) -> str:
        """Return the stable provider identifier."""
        return "openai"

    @property
    def model(self) -> str:
        """Return the configured OpenAI generation model."""
        return self._model

    async def generate(
        self,
        request: TextGenerationRequest,
    ) -> TextGenerationResult:
        """Generate one response through the OpenAI Responses API."""
        request.validate()

        try:
            response = await self._client.responses.create(
                model=self._model,
                instructions=request.system_prompt,
                input=request.user_prompt,
                max_output_tokens=self._max_output_tokens,
            )
        except Exception as exc:
            raise TextGenerationProviderError(
                "OpenAI generation request failed"
            ) from exc

        text = response.output_text.strip()
        result = TextGenerationResult(
            provider=self.provider,
            model=self.model,
            text=text,
        )
        result.validate()
        return result
