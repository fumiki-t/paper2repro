from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass
class PaperChunk:
    text: str
    page: int


class PaperEvidence(BaseModel):
    page: int
    excerpt: str


class ExperimentalClaim(BaseModel):
    statement: str
    evidence: list[PaperEvidence]
    dataset: str | None = None
    metric: str | None = None
    reported_value: str | None = None


class RepoArtifact(BaseModel):
    path: str
    artifact_type: str


class ClaimExtractionResult(BaseModel):
    claims: list[ExperimentalClaim]


class RepoDocument(BaseModel):
    path: str
    artifact_type: str
    content: str


class RepoEvidence(BaseModel):
    path: str
    artifact_type: str
    excerpt: str


MappingStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]
AuditStatus = Literal["PRESENT", "AMBIGUOUS", "NOT_FOUND"]
AuditCheck = Literal[
    "dataset_data_preparation",
    "model_config",
    "checkpoint",
    "training_or_inference_command",
    "environment_dependencies",
    "random_seed",
    "evaluation_protocol_metric",
]


class ClaimRepositoryMapping(BaseModel):
    status: MappingStatus
    evidence: list[RepoEvidence]
    explanation: str


class AuditItem(BaseModel):
    check: AuditCheck
    status: AuditStatus
    evidence: list[RepoEvidence]
    notes: str


class ClaimRepositoryAssessment(BaseModel):
    mapping: ClaimRepositoryMapping
    audit: list[AuditItem]


class PaperEvidenceCheck(BaseModel):
    page: int
    excerpt: str
    is_valid: bool
    reason: str | None = None


class RepoEvidenceCheck(BaseModel):
    evidence_index: int
    path: str
    excerpt: str
    is_valid: bool
    reason: str | None = None


class AuditEvidenceChecks(BaseModel):
    check: AuditCheck
    evidence: list[RepoEvidenceCheck]


class ClaimAnalysis(BaseModel):
    claim: ExperimentalClaim
    paper_evidence_validation: list[PaperEvidenceCheck]
    retrieved_documents: list[str]
    mapping: ClaimRepositoryMapping
    mapping_evidence_validation: list[RepoEvidenceCheck]
    audit: list[AuditItem]
    audit_evidence_validation: list[AuditEvidenceChecks]
    warnings: list[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    paper: str
    repository: str
    repository_artifact_count: int
    repository_document_count: int
    claims: list[ClaimAnalysis]
    warnings: list[str]
    limitations: list[str]
