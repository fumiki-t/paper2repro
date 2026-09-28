"""Google Gemini implementation of the structured LLM client interface."""

from collections.abc import Mapping
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from paper2repro.config import Settings
from paper2repro.models import LLMTokenUsage


OutputModel = TypeVar("OutputModel", bound=BaseModel)
_TOKEN_USAGE_FIELDS = (
    "total_input_tokens",
    "total_output_tokens",
    "total_thought_tokens",
    "total_cached_tokens",
    "total_tokens",
)


def _read_field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


class GeminiProviderError(RuntimeError):
    """Provider failure with a concise category; the SDK error remains ``__cause__``."""

    def __init__(self, category: str) -> None:
        self.provider = "Gemini"
        self.category = category
        super().__init__(f"Gemini request failed ({category}).")


def _error_category(error: Exception) -> str:
    name = type(error).__name__.lower()
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    status_text = str(status).lower()
    if (
        status == 429
        or "429" in status_text
        or "resourceexhausted" in name
        or "ratelimit" in name
    ):
        return "rate_limit"
    if status in {401, 403} or "unauthenticated" in name or "permissiondenied" in name:
        return "authentication_or_permission"
    if "timeout" in name or isinstance(error, TimeoutError):
        return "timeout"
    if "connection" in name or isinstance(error, ConnectionError):
        return "connection"
    return "provider_error"


class GeminiClient:
    """Generate Pydantic outputs with Gemini's JSON-schema constrained mode."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
    ) -> None:
        settings = settings or Settings.from_env()
        if client is None and not settings.api_key:
            raise ValueError("Set PAPER2REPRO_API_KEY before using GeminiClient.")

        self.model = settings.model
        self.last_token_usage: LLMTokenUsage | None = None
        self._client = client or genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    def generate_structured(
        self, prompt: str, response_model: type[OutputModel]
    ) -> OutputModel:
        """Ask Gemini for output constrained by the Pydantic JSON schema."""
        self.last_token_usage = None
        try:
            interaction = self._client.interactions.create(
                model=self.model,
                input=prompt,
                response_format=[
                    {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": response_model.model_json_schema(),
                    }
                ],
            )
        except Exception as error:
            raise GeminiProviderError(_error_category(error)) from error
        usage = _read_field(interaction, "usage")
        if usage is not None:
            self.last_token_usage = LLMTokenUsage(
                **{
                    field: (
                        value
                        if isinstance(value, int) and not isinstance(value, bool)
                        else None
                    )
                    for field in _TOKEN_USAGE_FIELDS
                    for value in [_read_field(usage, field)]
                }
            )
        output_text = interaction.output_text
        if not output_text:
            raise ValueError("Gemini returned no structured output text.")
        return response_model.model_validate_json(output_text)
