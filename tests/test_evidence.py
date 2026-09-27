from paper2repro.claims.evidence import validate_evidence
from paper2repro.models import (
    ClaimExtractionResult,
    ExperimentalClaim,
    PaperChunk,
    PaperEvidence,
)


def _result(page: int, excerpt: str) -> ClaimExtractionResult:
    return ClaimExtractionResult(
        claims=[
            ExperimentalClaim(
                statement="Method A achieves the reported score",
                evidence=[PaperEvidence(page=page, excerpt=excerpt)],
            )
        ]
    )


def test_evidence_page_and_exact_excerpt_are_valid() -> None:
    chunks = [PaperChunk(text="Our method achieves 72.4 mIoU.", page=3)]

    [validation] = validate_evidence(
        chunks, _result(3, "Our method achieves 72.4 mIoU.")
    )

    assert validation.is_valid
    assert validation.reason is None
    assert validation.claim_index == 1
    assert validation.evidence_index == 1


def test_evidence_allows_whitespace_differences() -> None:
    chunks = [PaperChunk(text="Our method\n achieves   72.4 mIoU.", page=3)]

    [validation] = validate_evidence(
        chunks, _result(3, "Our method achieves 72.4\n mIoU.")
    )

    assert validation.is_valid


def test_evidence_for_missing_page_is_invalid() -> None:
    chunks = [PaperChunk(text="Some paper text.", page=3)]

    [validation] = validate_evidence(chunks, _result(4, "Some paper text."))

    assert not validation.is_valid
    assert validation.reason == "page_not_found"


def test_hallucinated_excerpt_is_invalid() -> None:
    chunks = [PaperChunk(text="Our method achieves 72.4 mIoU.", page=3)]

    [validation] = validate_evidence(
        chunks, _result(3, "Our method achieves 99.9 mIoU.")
    )

    assert not validation.is_valid
    assert validation.reason == "excerpt_not_found"
