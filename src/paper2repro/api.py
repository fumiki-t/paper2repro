"""Minimal FastAPI entry point for the Paper2Repro pipeline."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from paper2repro.config import Settings
from paper2repro.logging_config import configure_logging
from paper2repro.pipeline import analyze
from paper2repro.providers.gemini import GeminiClient
from paper2repro.report import write_analysis_report
from paper2repro.repo.source import RepositorySourceError

configure_logging()

app = FastAPI(title="Paper2Repro", version="0.1.0")


class AnalysisRequest(BaseModel):
    paper_path: str
    repository: str
    output_dir: str = "outputs/api"
    top_k: int = Field(default=5, ge=1)


def get_llm_client() -> GeminiClient:
    try:
        return GeminiClient(Settings.from_env())
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analysis")
def create_analysis(
    request: AnalysisRequest,
    llm_client=Depends(get_llm_client),
) -> dict:
    """Run the synchronous v0.1 pipeline for local server-controlled paths."""
    paper_path = Path(request.paper_path).expanduser()
    if not paper_path.is_file():
        raise HTTPException(status_code=400, detail="Paper PDF was not found.")

    try:
        report = analyze(
            paper_path,
            request.repository,
            llm_client,
            top_k=request.top_k,
        )
        json_path, markdown_path = write_analysis_report(
            report, Path(request.output_dir).expanduser()
        )
    except (RepositorySourceError, OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "report": report.model_dump(mode="json"),
        "outputs": {
            "json": str(json_path),
            "markdown": str(markdown_path),
        },
    }
