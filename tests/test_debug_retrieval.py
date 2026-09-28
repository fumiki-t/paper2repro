from pathlib import Path
import os
import subprocess
import sys

from paper2repro.models import (
    AnalysisReport,
    AuditItem,
    ClaimAnalysis,
    ClaimRepositoryMapping,
    ExperimentalClaim,
)


SCRIPT = Path(__file__).parents[1] / "scripts" / "debug_retrieval.py"


def test_debug_cli_shows_zero_retrieval_without_constructing_llm(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("unrelated content", encoding="utf-8")
    report = AnalysisReport(
        paper="paper.pdf",
        repository="repository",
        repository_artifact_count=1,
        repository_document_count=1,
        claims=[
            ClaimAnalysis(
                claim=ExperimentalClaim(
                    statement="A result on an unseen dataset.",
                    evidence=[],
                    dataset="unseen-dataset",
                    metric="unseen-metric",
                    reported_value="999.9",
                ),
                paper_evidence_validation=[],
                retrieved_documents=[],
                mapping=ClaimRepositoryMapping(
                    status="UNSUPPORTED", evidence=[], explanation="No candidates."
                ),
                mapping_evidence_validation=[],
                audit=[
                    AuditItem(
                        check="model_config",
                        status="NOT_FOUND",
                        evidence=[],
                        notes="No documents were retrieved.",
                    )
                ],
                audit_evidence_validation=[],
            )
        ],
        warnings=[],
        limitations=[],
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(report.model_dump_json(), encoding="utf-8")
    env = os.environ.copy()
    source_path = str(SCRIPT.parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        [source_path, env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report_path),
            "--repo",
            str(repository),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "LLM calls: 0" in output
    assert "No retrieved documents (all scores were 0)." in output
    assert "dataset='unseen-dataset'" in output


def test_debug_cli_compares_retrievers_and_shows_weighted_matches(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text(
        "The lightweight decoder is used here.", encoding="utf-8"
    )
    report = AnalysisReport(
        paper="paper.pdf",
        repository="repository",
        repository_artifact_count=1,
        repository_document_count=1,
        claims=[
            ClaimAnalysis(
                claim=ExperimentalClaim(
                    statement="The lightweight decoder is used here.",
                    evidence=[],
                ),
                paper_evidence_validation=[],
                retrieved_documents=[],
                mapping=ClaimRepositoryMapping(
                    status="UNSUPPORTED", evidence=[], explanation="Review only."
                ),
                mapping_evidence_validation=[],
                audit=[],
                audit_evidence_validation=[],
            )
        ],
        warnings=[],
        limitations=[],
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(report.model_dump_json(), encoding="utf-8")
    env = os.environ.copy()
    source_path = str(SCRIPT.parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        [source_path, env.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report_path),
            "--repo",
            str(repository),
            "--compare",
            "--claims",
            "1",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "LLM calls: 0" in result.stdout
    assert "Baseline top-0:" in result.stdout
    assert "Weighted top-1:" in result.stdout
    assert "README.md" in result.stdout
    assert "matched terms: lightweight (body +1)" in result.stdout
