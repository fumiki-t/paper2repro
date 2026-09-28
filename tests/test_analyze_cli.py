import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from pypdf import PdfWriter

from paper2repro.config import Settings
from paper2repro.providers.gemini import GeminiProviderError


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze.py"


def test_end_to_end_cli_reports_missing_api_key(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)
    repository = tmp_path / "repository"
    repository.mkdir()

    env = os.environ.copy()
    env.pop("PAPER2REPRO_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--paper",
            str(pdf_path),
            "--repo",
            str(repository),
            "--retriever",
            "weighted",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "PAPER2REPRO_API_KEY is not set" in result.stderr


def test_cli_reports_missing_claim_source_before_api_key_check(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)
    repository = tmp_path / "repository"
    repository.mkdir()
    missing_report = tmp_path / "missing-report.json"

    env = os.environ.copy()
    env.pop("PAPER2REPRO_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--paper",
            str(pdf_path),
            "--repo",
            str(repository),
            "--reuse-claims-from",
            str(missing_report),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "Claim source report does not exist or is not a file" in result.stderr
    assert "PAPER2REPRO_API_KEY is not set" not in result.stderr


def test_cli_prints_safe_provider_rate_limit_detail(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    spec = importlib.util.spec_from_file_location(
        "paper2repro_analyze_script", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    analyze_script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyze_script)

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"mock pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    settings = Settings(api_key="test-key", model="test-model")
    monkeypatch.setattr(analyze_script.Settings, "from_env", lambda *args: settings)
    monkeypatch.setattr(analyze_script, "GeminiClient", lambda settings: object())

    def rate_limited(*args, **kwargs):
        raise GeminiProviderError(
            "rate_limit",
            provider_code=429,
            provider_message="Requests per minute quota exceeded.",
        )

    monkeypatch.setattr(analyze_script, "analyze", rate_limited)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--paper", str(pdf_path), "--repo", str(repository)],
    )

    assert analyze_script.main() == 1
    error_text = capsys.readouterr().err
    assert "Gemini error (category: rate_limit):" in error_text
    assert "code 429: Requests per minute quota exceeded." in error_text
    assert "No automatic retry was attempted." in error_text
