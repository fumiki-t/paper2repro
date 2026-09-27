"""End-to-end Paper2Repro analysis workflow."""

from dataclasses import asdict
from pathlib import Path

from paper2repro.claims.evidence import validate_evidence
from paper2repro.claims.extractor import extract_claims
from paper2repro.llm import LLMClient
from paper2repro.mapping.assessor import assess_claim_repository
from paper2repro.models import (
    AnalysisReport,
    AuditEvidenceChecks,
    ClaimAnalysis,
    PaperEvidenceCheck,
    RepoEvidenceCheck,
)
from paper2repro.pdf import parse_pdf
from paper2repro.repo.inventory import inventory_repository
from paper2repro.repo.loader import load_repository_documents
from paper2repro.repo.source import repository_source
from paper2repro.retrieval.keyword import retrieve_documents


DEFAULT_LIMITATIONS = [
    "Evidence validation checks textual anchoring, not semantic entailment.",
    "Keyword retrieval is a simple lexical baseline over dataset, metric, and value.",
    "NOT_FOUND means not found in the inspected retrieved artifacts, not proven absent.",
    "Paper2Repro does not execute training, inference, or evaluation commands.",
]


def analyze(
    paper_path: Path,
    repository: str | Path,
    llm_client: LLMClient,
    *,
    top_k: int = 5,
) -> AnalysisReport:
    """Run claim extraction, repository mapping, and audit for one paper/repo pair."""
    chunks = parse_pdf(paper_path)
    extracted = extract_claims(chunks, llm_client)
    paper_validations = validate_evidence(chunks, extracted)
    validations_by_claim: dict[int, list[PaperEvidenceCheck]] = {}
    for validation in paper_validations:
        validations_by_claim.setdefault(validation.claim_index, []).append(
            PaperEvidenceCheck(**asdict(validation))
        )

    with repository_source(repository) as repository_path:
        artifacts = inventory_repository(repository_path)
        documents = load_repository_documents(repository_path, artifacts)

        claim_analyses: list[ClaimAnalysis] = []
        report_warnings: list[str] = []
        for claim_index, claim in enumerate(extracted.claims, start=1):
            retrieved = retrieve_documents(claim, documents, top_k=top_k)
            grounded = assess_claim_repository(claim, retrieved, llm_client)
            warnings = [
                f"Claim {claim_index}: {warning}" for warning in grounded.warnings
            ]
            report_warnings.extend(warnings)
            claim_analyses.append(
                ClaimAnalysis(
                    claim=claim,
                    paper_evidence_validation=validations_by_claim.get(
                        claim_index, []
                    ),
                    retrieved_documents=[document.path for document in retrieved],
                    mapping=grounded.assessment.mapping,
                    mapping_evidence_validation=[
                        RepoEvidenceCheck(**asdict(validation))
                        for validation in grounded.mapping_validation
                    ],
                    audit=grounded.assessment.audit,
                    audit_evidence_validation=[
                        AuditEvidenceChecks(
                            check=check,
                            evidence=[
                                RepoEvidenceCheck(**asdict(validation))
                                for validation in validations
                            ],
                        )
                        for check, validations in grounded.audit_validation.items()
                    ],
                    warnings=warnings,
                )
            )

    invalid_paper_evidence = sum(
        not check.is_valid
        for claim in claim_analyses
        for check in claim.paper_evidence_validation
    )
    if invalid_paper_evidence:
        report_warnings.insert(
            0,
            f"{invalid_paper_evidence} paper evidence excerpt(s) could not be anchored "
            "to the cited page.",
        )

    return AnalysisReport(
        paper=str(paper_path),
        repository=str(repository),
        repository_artifact_count=len(artifacts),
        repository_document_count=len(documents),
        claims=claim_analyses,
        warnings=report_warnings,
        limitations=DEFAULT_LIMITATIONS,
    )
