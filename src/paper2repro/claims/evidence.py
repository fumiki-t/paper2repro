"""Deterministic validation that paper evidence quotes source page text."""

from dataclasses import dataclass
import re

from paper2repro.models import ClaimExtractionResult, PaperChunk


@dataclass(frozen=True)
class EvidenceValidation:
    """Validation result for one evidence item (indices are 1-based)."""

    claim_index: int
    evidence_index: int
    page: int
    excerpt: str
    is_valid: bool
    reason: str | None = None


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_evidence(
    chunks: list[PaperChunk], result: ClaimExtractionResult
) -> list[EvidenceValidation]:
    """Check that each excerpt appears on the cited input page.

    Whitespace runs are normalized before comparison to accommodate PDF text
    extraction line breaks. This checks textual grounding only; it does not
    judge whether the excerpt semantically supports the claim.
    """
    page_text = {chunk.page: _normalize_whitespace(chunk.text) for chunk in chunks}
    validations: list[EvidenceValidation] = []

    for claim_index, claim in enumerate(result.claims, start=1):
        for evidence_index, evidence in enumerate(claim.evidence, start=1):
            if evidence.page not in page_text:
                is_valid = False
                reason = "page_not_found"
            else:
                excerpt = _normalize_whitespace(evidence.excerpt)
                if not excerpt:
                    is_valid = False
                    reason = "empty_excerpt"
                elif excerpt in page_text[evidence.page]:
                    is_valid = True
                    reason = None
                else:
                    is_valid = False
                    reason = "excerpt_not_found"

            validations.append(
                EvidenceValidation(
                    claim_index=claim_index,
                    evidence_index=evidence_index,
                    page=evidence.page,
                    excerpt=evidence.excerpt,
                    is_valid=is_valid,
                    reason=reason,
                )
            )

    return validations
