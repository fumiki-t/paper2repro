"""Deterministic validation that paper evidence quotes source page text."""

from dataclasses import dataclass
import re
import unicodedata

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


_LINE_BREAK_HYPHENATION = re.compile(
    r"(?<=[^\W\d_])[-\u2010]\s*\n\s*(?=[^\W\d_])"
)


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = _LINE_BREAK_HYPHENATION.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


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
    page_text = {chunk.page: _normalize_text(chunk.text) for chunk in chunks}
    compact_page_text = {
        page: re.sub(r"\s+", "", text) for page, text in page_text.items()
    }
    validations: list[EvidenceValidation] = []

    for claim_index, claim in enumerate(result.claims, start=1):
        for evidence_index, evidence in enumerate(claim.evidence, start=1):
            if evidence.page not in page_text:
                is_valid = False
                reason = "page_not_found"
            else:
                excerpt = _normalize_text(evidence.excerpt)
                if not excerpt:
                    is_valid = False
                    reason = "empty_excerpt"
                elif excerpt in page_text[evidence.page]:
                    is_valid = True
                    reason = None
                elif (
                    re.sub(r"\s+", "", excerpt)
                    in compact_page_text[evidence.page]
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
