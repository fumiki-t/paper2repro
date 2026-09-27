from types import SimpleNamespace

from paper2repro.config import Settings
from paper2repro.models import ClaimExtractionResult
from paper2repro.providers.gemini import GeminiClient, GeminiProviderError


class FakeInteractions:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text)


class FakeGeminiSDKClient:
    def __init__(self, output_text: str) -> None:
        self.interactions = FakeInteractions(output_text)


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
