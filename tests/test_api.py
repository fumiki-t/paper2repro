from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from paper2repro.api import app, get_llm_client
from paper2repro.models import ClaimExtractionResult


class EmptyClaimClient:
    def generate_structured(self, prompt, response_model):
        assert response_model is ClaimExtractionResult
        return ClaimExtractionResult(claims=[])


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analysis_endpoint_runs_pipeline_without_real_gemini(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("setup", encoding="utf-8")
    output_dir = tmp_path / "output"
    app.dependency_overrides[get_llm_client] = lambda: EmptyClaimClient()

    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "paper_path": str(pdf_path),
                "repository": str(repository),
                "output_dir": str(output_dir),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["report"]["claims"] == []
    assert (output_dir / "report.json").is_file()
    assert (output_dir / "report.md").is_file()


def test_analysis_endpoint_explains_missing_api_key(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("PAPER2REPRO_API_KEY", raising=False)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"not read because dependency fails first")

    response = TestClient(app).post(
        "/analysis",
        json={"paper_path": str(pdf_path), "repository": str(tmp_path)},
    )

    assert response.status_code == 503
    assert "PAPER2REPRO_API_KEY" in response.json()["detail"]
