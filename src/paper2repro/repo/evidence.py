"""Deterministic grounding checks for repository evidence."""

from dataclasses import dataclass

from paper2repro.models import RepoDocument, RepoEvidence
from paper2repro.text import contains_normalized_excerpt, normalize_extracted_text


@dataclass(frozen=True)
class RepoEvidenceValidation:
    evidence_index: int
    path: str
    excerpt: str
    is_valid: bool
    reason: str | None = None


def validate_repo_evidence(
    documents: list[RepoDocument], evidence: list[RepoEvidence]
) -> list[RepoEvidenceValidation]:
    """Check that each excerpt anchors to the cited retrieved document."""
    documents_by_path = {document.path: document for document in documents}
    validations: list[RepoEvidenceValidation] = []

    for evidence_index, item in enumerate(evidence, start=1):
        document = documents_by_path.get(item.path)
        if document is None:
            is_valid = False
            reason = "path_not_retrieved"
        elif not normalize_extracted_text(item.excerpt):
            is_valid = False
            reason = "empty_excerpt"
        elif contains_normalized_excerpt(document.content, item.excerpt):
            is_valid = True
            reason = None
        else:
            is_valid = False
            reason = "excerpt_not_found"

        validations.append(
            RepoEvidenceValidation(
                evidence_index=evidence_index,
                path=item.path,
                excerpt=item.excerpt,
                is_valid=is_valid,
                reason=reason,
            )
        )

    return validations
