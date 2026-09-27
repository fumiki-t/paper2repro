"""Provider-neutral interface for future structured LLM calls."""

from typing import Protocol, TypeVar

from pydantic import BaseModel


OutputModel = TypeVar("OutputModel", bound=BaseModel)


class LLMClient(Protocol):
    """Interface for an LLM that can return a Pydantic model."""

    def generate_structured(
        self, prompt: str, response_model: type[OutputModel]
    ) -> OutputModel:
        """Generate structured output matching ``response_model``.

        Provider implementations should parse their response with
        ``response_model.model_validate(...)``. Claim extraction behavior is
        intentionally left to a later implementation.
        """
        ...
