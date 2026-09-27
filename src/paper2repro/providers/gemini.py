"""Google Gemini implementation of the structured LLM client interface."""

from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel

from paper2repro.config import Settings


OutputModel = TypeVar("OutputModel", bound=BaseModel)


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
        self._client = client or genai.Client(api_key=settings.api_key)

    def generate_structured(
        self, prompt: str, response_model: type[OutputModel]
    ) -> OutputModel:
        """Ask Gemini for output constrained by the Pydantic JSON schema."""
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
        output_text = interaction.output_text
        if not output_text:
            raise ValueError("Gemini returned no structured output text.")
        return response_model.model_validate_json(output_text)
