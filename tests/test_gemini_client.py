from types import SimpleNamespace

from paper2repro.config import Settings
from paper2repro.models import ClaimExtractionResult
from paper2repro.providers.gemini import GeminiClient


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
