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


class LLMTokenUsage(BaseModel):
    """Provider-reported token counts for one structured LLM request."""

    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_thought_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_tokens: int | None = None


class LLMRequestMetric(BaseModel):
    model: str
    response_model: str
    prompt_characters: int
    response_characters: int
    elapsed_seconds: float
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_thought_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_tokens: int | None = None


class ClaimRuntimeMetric(BaseModel):
    claim_index: int
    retrieval_seconds: float
    mapping_audit_seconds: float
    total_seconds: float
    cache_hit: bool


class PerformanceMetrics(BaseModel):
    total_elapsed_seconds: float | None = None
    pdf_parsing_seconds: float | None = None
    claim_extraction_seconds: float | None = None
    repository_preparation_seconds: float | None = None
    inventory_loading_seconds: float | None = None
    retrieval_seconds_total: float | None = None
    report_generation_seconds: float | None = None
    llm_request_count: int | None = None
    prompt_characters_total: int | None = None
    response_characters_total: int | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_thought_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_tokens: int | None = None
    cache_hits: int | None = None
    cache_misses: int | None = None
    llm_requests: list[LLMRequestMetric] = Field(default_factory=list)
    claims: list[ClaimRuntimeMetric] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    paper: str
    repository: str
    retriever: Literal["baseline", "weighted"] = "baseline"
    claim_source: Literal["llm", "reused_report"] = "llm"
    claim_source_path: str | None = None
    repository_artifact_count: int
    repository_document_count: int
    claims: list[ClaimAnalysis]
    warnings: list[str]
    limitations: list[str]
    performance: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
