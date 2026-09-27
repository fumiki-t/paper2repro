from paper2repro.claims.extractor import extract_claims
from paper2repro.models import ClaimExtractionResult, PaperChunk


class RecordingLLMClient:
    def __init__(self) -> None:
        self.prompt = ""
        self.response_model = None

    def generate_structured(self, prompt, response_model):
        self.prompt = prompt
        self.response_model = response_model
        return response_model(claims=[])


def test_extractor_sends_page_tagged_prompt_and_returns_result() -> None:
    client = RecordingLLMClient()

    result = extract_claims([PaperChunk(text="A result.", page=7)], client)

    assert isinstance(result, ClaimExtractionResult)
    assert client.response_model is ClaimExtractionResult
    assert "[PAGE 7]\nA result." in client.prompt
    assert "verbatim passage" in client.prompt
    assert "Keep claims atomic" in client.prompt
    assert "different tasks or metrics into separate claims" in client.prompt
