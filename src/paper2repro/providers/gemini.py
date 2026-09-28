"""Google Gemini implementation of the structured LLM client interface."""

import re
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

    def __init__(
        self,
        category: str,
        *,
        provider_code: int | str | None = None,
        provider_message: str | None = None,
    ) -> None:
        self.provider = "Gemini"
        self.category = category
        self.provider_code = provider_code
        self.provider_message = provider_message
        super().__init__(f"Gemini request failed ({category}).")


def _redact_secrets(message: str) -> str:
    safe_message = message
    safe_message = re.sub(
        (
            r"(?i)\b(api[_ -]?key|access[_ -]?token|client[_ -]?secret|"
            r"secret|password|token|authorization)\b"
            r"[\"']?\s*[:=]\s*[\"']?[^\s,\"'}]+"
        ),
        r"\1=[REDACTED]",
        safe_message,
    )
    safe_message = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", safe_message
    )
    safe_message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED]", safe_message)
    safe_message = re.sub(
        r"(?i)([?&](?:key|api_key|access_token)=)[^&#\s]+",
        r"\1[REDACTED]",
        safe_message,
    )
    return safe_message


def _quota_identifiers(value: Any) -> list[str]:
    found: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in {"quotaMetric", "quotaId"} and isinstance(child, str):
                    identifier = _redact_secrets(child.strip())[:160]
                    if identifier and identifier not in found:
                        found.append(identifier)
                elif isinstance(child, (Mapping, list, tuple)):
                    visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found[:6]


def _safe_provider_message(error: Exception) -> str | None:
    parts: list[str] = []
    message = getattr(error, "message", None)
    if isinstance(message, str) and message.strip():
        parts.append(_redact_secrets(message.strip()))
    for identifier in _quota_identifiers(getattr(error, "details", None)):
        if not any(identifier in part for part in parts):
            parts.append(f"quota identifier: {identifier}")
    if not parts:
        return None
    return "; ".join(parts)[:1200]


def _provider_code(error: Exception) -> int | str | None:
    code = getattr(error, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        return code
    if isinstance(code, str):
        if re.fullmatch(r"\d{1,5}|[A-Z][A-Z0-9_.-]{1,63}", code):
            return code
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        return status_code
    return None


def _error_category(error: Exception) -> str:
    name = type(error).__name__.lower()
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    status_text = str(status).lower()
    if (
        status == 429
        or "429" in status_text
        or "resource_exhausted" in status_text
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
            raise GeminiProviderError(
                _error_category(error),
                provider_code=_provider_code(error),
                provider_message=_safe_provider_message(error),
            ) from error
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
