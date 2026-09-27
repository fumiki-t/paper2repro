"""Deterministic validation that paper evidence quotes source page text."""

from dataclasses import dataclass

from paper2repro.models import ClaimExtractionResult, PaperChunk
from paper2repro.text import contains_normalized_excerpt, normalize_extracted_text


@dataclass(frozen=True)
class EvidenceValidation:
    """Validation result for one evidence item (indices are 1-based)."""

    claim_index: int
    evidence_index: int
    page: int
    excerpt: str
    is_valid: bool
    reason: str | None = None


def validate_evidence(
    chunks: list[PaperChunk], result: ClaimExtractionResult
) -> list[EvidenceValidation]:
    """Check that each excerpt appears on the cited input page.

    Validation means only that the requested excerpt can be anchored to text
    extracted from the cited PDF page. It does not determine whether that
    excerpt semantically supports the claim. Text is normalized with Unicode
    NFKC, invisible format-character removal, line-break hyphenation repair,
    and whitespace collapsing. If direct substring matching fails, a second
    comparison ignores whitespace only; characters, digits, and punctuation
    remain significant.
    """
    page_text = {chunk.page: chunk.text for chunk in chunks}
    validations: list[EvidenceValidation] = []

    for claim_index, claim in enumerate(result.claims, start=1):
        for evidence_index, evidence in enumerate(claim.evidence, start=1):
            if evidence.page not in page_text:
                is_valid = False
                reason = "page_not_found"
            else:
                excerpt = normalize_extracted_text(evidence.excerpt)
                if not excerpt:
                    is_valid = False
                    reason = "empty_excerpt"
                elif contains_normalized_excerpt(
                    page_text[evidence.page], evidence.excerpt
                ):
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
