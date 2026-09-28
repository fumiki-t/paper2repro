"""Small runtime instrumentation for one Paper2Repro analysis."""

from __future__ import annotations

from time import perf_counter
from typing import TypeVar

from pydantic import BaseModel

from paper2repro.cache import AnalysisCache
from paper2repro.llm import LLMClient
from paper2repro.models import LLMRequestMetric, LLMTokenUsage


OutputModel = TypeVar("OutputModel", bound=BaseModel)


class LLMCallBudgetExceeded(RuntimeError):
    """Raised before an LLM request would exceed the user's optional budget."""


class InstrumentedLLMClient:
    """Count requests and capture text lengths, optional token usage, and time."""

    def __init__(
        self,
        client: LLMClient,
        *,
        model_name: str,
        max_calls: int | None = None,
    ) -> None:
        self.client = client
        self.model_name = model_name
        self.max_calls = max_calls
        self.requests: list[LLMRequestMetric] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def generate_structured(
        self, prompt: str, response_model: type[OutputModel]
    ) -> OutputModel:
        if self.max_calls is not None and self.call_count >= self.max_calls:
            raise LLMCallBudgetExceeded(
                f"LLM call budget ({self.max_calls}) reached; the next request "
                "was blocked before contacting the provider."
            )

        started = perf_counter()
        response_characters = 0
        try:
            result = self.client.generate_structured(prompt, response_model)
            response_characters = len(result.model_dump_json())
            return result
        finally:
            token_usage = getattr(self.client, "last_token_usage", None)
            token_fields = (
                token_usage.model_dump()
                if isinstance(token_usage, LLMTokenUsage)
                else {}
            )
            self.requests.append(
                LLMRequestMetric(
                    model=self.model_name,
                    response_model=response_model.__name__,
                    prompt_characters=len(prompt),
                    response_characters=response_characters,
                    elapsed_seconds=perf_counter() - started,
                    **token_fields,
                )
            )


class CachedLLMClient:
    """Add per-call JSON caching while preserving the provider-neutral interface."""

    def __init__(
        self, client: LLMClient, cache: AnalysisCache | None = None
    ) -> None:
        self.client = client
        self.cache = cache
        self.metadata: dict[str, object] | None = None
        self.cache_hits = 0
        self.cache_misses = 0

    def prepare_cache_key(self, metadata: dict[str, object]) -> None:
        self.metadata = metadata

    def generate_structured(
        self, prompt: str, response_model: type[OutputModel]
    ) -> OutputModel:
        if self.cache is None or self.metadata is None:
            return self.client.generate_structured(prompt, response_model)

        cached = self.cache.get(self.metadata, response_model)
        if cached is not None:
            self.cache_hits += 1
            return cached

        self.cache_misses += 1
        result = self.client.generate_structured(prompt, response_model)
        self.cache.put(self.metadata, result)
        return result
