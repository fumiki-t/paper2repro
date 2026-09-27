import os
from pathlib import Path
import subprocess
import sys

from pypdf import PdfWriter


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_pdf_claims.py"


def test_cli_reports_missing_pdf() -> None:
    env = os.environ.copy()
    env.pop("PAPER2REPRO_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "missing-paper.pdf"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "PDF file does not exist" in result.stderr


def test_cli_reports_missing_api_key(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)

    env = os.environ.copy()
    env.pop("PAPER2REPRO_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(pdf_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "PAPER2REPRO_API_KEY is not set" in result.stderr
