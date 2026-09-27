from dataclasses import dataclass

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
