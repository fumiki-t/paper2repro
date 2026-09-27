from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class PaperChunk:
    text: str
    page: int

class ExperimentalClaim(BaseModel):
    statement: str
    page: int

class RepoArtifact(BaseModel):
    path: str
    artifact_type: str