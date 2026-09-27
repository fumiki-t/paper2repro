"""Claim extraction orchestration, independent of any one provider."""

from paper2repro.claims.prompts import build_claim_extraction_prompt
from paper2repro.llm import LLMClient
from paper2repro.models import ClaimExtractionResult, PaperChunk


def extract_claims(
    chunks: list[PaperChunk], llm_client: LLMClient
) -> ClaimExtractionResult:
    """Extract structured experimental claims from page-tagged paper chunks."""
    prompt = build_claim_extraction_prompt(chunks)
    return llm_client.generate_structured(prompt, ClaimExtractionResult)
