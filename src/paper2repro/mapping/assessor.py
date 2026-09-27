"""LLM assessment plus deterministic repository evidence grounding."""

from dataclasses import dataclass

from paper2repro.llm import LLMClient
from paper2repro.mapping.prompts import build_repository_assessment_prompt
from paper2repro.models import (
    AuditCheck,
    AuditItem,
    ClaimRepositoryAssessment,
    ClaimRepositoryMapping,
    ExperimentalClaim,
    RepoDocument,
)
from paper2repro.repo.evidence import RepoEvidenceValidation, validate_repo_evidence


AUDIT_CHECKS: tuple[AuditCheck, ...] = (
    "dataset_data_preparation",
    "model_config",
    "checkpoint",
    "training_or_inference_command",
    "environment_dependencies",
    "random_seed",
    "evaluation_protocol_metric",
)


@dataclass(frozen=True)
class GroundedRepositoryAssessment:
    assessment: ClaimRepositoryAssessment
    mapping_validation: list[RepoEvidenceValidation]
    audit_validation: dict[str, list[RepoEvidenceValidation]]
    warnings: list[str]


def _empty_assessment() -> ClaimRepositoryAssessment:
    return ClaimRepositoryAssessment(
        mapping=ClaimRepositoryMapping(
            status="UNSUPPORTED",
            evidence=[],
            explanation="No repository documents matched the claim keywords.",
        ),
        audit=[
            AuditItem(
                check=check,
                status="NOT_FOUND",
                evidence=[],
                notes="No matching repository documents were retrieved.",
            )
            for check in AUDIT_CHECKS
        ],
    )


def _complete_audit(audit: list[AuditItem]) -> list[AuditItem]:
    by_check: dict[str, AuditItem] = {}
    for item in audit:
        by_check.setdefault(item.check, item)
    return [
        by_check.get(check)
        or AuditItem(
            check=check,
            status="NOT_FOUND",
            evidence=[],
            notes="The model did not return this required audit item.",
        )
        for check in AUDIT_CHECKS
    ]


def assess_claim_repository(
    claim: ExperimentalClaim,
    documents: list[RepoDocument],
    llm_client: LLMClient,
) -> GroundedRepositoryAssessment:
    """Assess one claim and downgrade claims unsupported by anchored evidence."""
    if not documents:
        assessment = _empty_assessment()
    else:
        prompt = build_repository_assessment_prompt(claim, documents)
        assessment = llm_client.generate_structured(
            prompt, ClaimRepositoryAssessment
        )
        assessment = assessment.model_copy(
            update={"audit": _complete_audit(assessment.audit)}
        )

    warnings: list[str] = []
    mapping_validation = validate_repo_evidence(
        documents, assessment.mapping.evidence
    )
    has_valid_mapping_evidence = any(item.is_valid for item in mapping_validation)
    if assessment.mapping.status != "UNSUPPORTED" and not has_valid_mapping_evidence:
        warnings.append(
            "Mapping status was downgraded because no repository evidence could be anchored."
        )
        assessment.mapping = assessment.mapping.model_copy(
            update={"status": "UNSUPPORTED"}
        )

    audit_validation: dict[str, list[RepoEvidenceValidation]] = {}
    grounded_audit: list[AuditItem] = []
    for item in assessment.audit:
        validations = validate_repo_evidence(documents, item.evidence)
        audit_validation[item.check] = validations
        has_valid_evidence = any(validation.is_valid for validation in validations)
        if item.status == "PRESENT" and not has_valid_evidence:
            replacement = "AMBIGUOUS" if item.evidence else "NOT_FOUND"
            warnings.append(
                f"Audit item {item.check} was downgraded to {replacement} because "
                "no evidence could be anchored."
            )
            item = item.model_copy(update={"status": replacement})
        grounded_audit.append(item)
    assessment.audit = grounded_audit

    return GroundedRepositoryAssessment(
        assessment=assessment,
        mapping_validation=mapping_validation,
        audit_validation=audit_validation,
        warnings=warnings,
    )
