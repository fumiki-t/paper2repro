from types import SimpleNamespace

from paper2repro.config import Settings
from paper2repro.models import ClaimExtractionResult
from paper2repro.providers.gemini import GeminiClient, GeminiProviderError


class FakeInteractions:
    def __init__(self, output_text: str, usage=None) -> None:
        self.output_text = output_text
        self.usage = usage
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text, usage=self.usage)


class FakeGeminiSDKClient:
    def __init__(self, output_text: str, usage=None) -> None:
        self.interactions = FakeInteractions(output_text, usage)


def test_gemini_client_uses_schema_constrained_output_and_validates_model() -> None:
    sdk_client = FakeGeminiSDKClient('{"claims": []}')
    client = GeminiClient(
        Settings(api_key="test-key", model="gemini-test-model"),
        client=sdk_client,
    )

    result = client.generate_structured("extract", ClaimExtractionResult)

    assert isinstance(result, ClaimExtractionResult)
    assert result.claims == []
    assert sdk_client.interactions.kwargs["model"] == "gemini-test-model"
    assert sdk_client.interactions.kwargs["input"] == "extract"
    response_format = sdk_client.interactions.kwargs["response_format"]
    assert response_format[0]["mime_type"] == "application/json"
    assert response_format[0]["schema"] == ClaimExtractionResult.model_json_schema()
    assert client.last_token_usage is None


def test_gemini_client_records_interaction_usage_fields() -> None:
    sdk_client = FakeGeminiSDKClient(
        '{"claims": []}',
        usage={
            "total_input_tokens": 100,
            "total_output_tokens": 20,
            "total_thought_tokens": 5,
            "total_cached_tokens": 10,
            "total_tokens": 125,
        },
    )
    client = GeminiClient(Settings(api_key="test-key"), client=sdk_client)

    client.generate_structured("extract", ClaimExtractionResult)

    assert client.last_token_usage is not None
    assert client.last_token_usage.model_dump() == {
        "total_input_tokens": 100,
        "total_output_tokens": 20,
        "total_thought_tokens": 5,
        "total_cached_tokens": 10,
        "total_tokens": 125,
    }


def test_gemini_client_accepts_object_usage_with_missing_counts() -> None:
    usage = SimpleNamespace(total_input_tokens=12, total_output_tokens=3)
    sdk_client = FakeGeminiSDKClient('{"claims": []}', usage=usage)
    client = GeminiClient(Settings(api_key="test-key"), client=sdk_client)

    client.generate_structured("extract", ClaimExtractionResult)

    assert client.last_token_usage is not None
    assert client.last_token_usage.total_input_tokens == 12
    assert client.last_token_usage.total_output_tokens == 3
    assert client.last_token_usage.total_thought_tokens is None
    assert client.last_token_usage.total_cached_tokens is None
    assert client.last_token_usage.total_tokens is None


def test_gemini_client_requires_api_key_without_injected_client() -> None:
    try:
        GeminiClient(Settings(api_key=None))
    except ValueError as error:
        assert "PAPER2REPRO_API_KEY" in str(error)
    else:
        raise AssertionError("GeminiClient should require an API key")


def test_gemini_client_disables_sdk_retries_by_default(monkeypatch) -> None:
    sdk_client = FakeGeminiSDKClient('{"claims": []}')
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return sdk_client

    monkeypatch.setattr("paper2repro.providers.gemini.genai.Client", fake_client)
    GeminiClient(Settings(api_key="test-key"))

    assert captured["http_options"].retry_options.attempts == 1


def test_gemini_client_wraps_provider_error_and_preserves_cause() -> None:
    class RateLimitError(Exception):
        status_code = 429

    class FailingInteractions:
        def create(self, **kwargs):
            raise RateLimitError("provider detail")

    class FailingClient:
        interactions = FailingInteractions()

    client = GeminiClient(Settings(api_key="test-key"), client=FailingClient())
    try:
        client.generate_structured("prompt", ClaimExtractionResult)
    except GeminiProviderError as error:
        assert error.provider == "Gemini"
        assert error.category == "rate_limit"
        assert isinstance(error.__cause__, RateLimitError)
    else:
        raise AssertionError("Gemini provider error should have been wrapped")
