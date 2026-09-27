from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


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
