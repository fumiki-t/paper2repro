from pathlib import Path

from paper2repro.models import (
    AuditItem,
    ClaimExtractionResult,
    ClaimRepositoryAssessment,
    ClaimRepositoryMapping,
    ExperimentalClaim,
    PaperChunk,
    PaperEvidence,
    RepoEvidence,
)
from paper2repro.pipeline import analyze
from paper2repro.report import write_analysis_report


class PipelineLLMClient:
    def generate_structured(self, prompt, response_model):
        if response_model is ClaimExtractionResult:
            return ClaimExtractionResult(
                claims=[
                    ExperimentalClaim(
                        statement="The method reaches 72.4 mAP on SoccerNet.",
                        evidence=[
                            PaperEvidence(
                                page=1,
                                excerpt="The method reaches 72.4 mAP on SoccerNet.",
                            )
                        ],
                        dataset="SoccerNet",
                        metric="mAP",
                        reported_value="72.4",
                    )
                ]
            )
        if response_model is ClaimRepositoryAssessment:
            evidence = RepoEvidence(
                path="README.md",
                artifact_type="readme",
                excerpt="Evaluate SoccerNet mAP 72.4 with python evaluate.py",
            )
            return ClaimRepositoryAssessment(
                mapping=ClaimRepositoryMapping(
                    status="SUPPORTED",
                    evidence=[evidence],
                    explanation="The README provides an evaluation command.",
                ),
                audit=[
                    AuditItem(
                        check="evaluation_protocol_metric",
                        status="PRESENT",
                        evidence=[evidence],
                        notes="Metric and command are documented.",
                    )
                ],
            )
        raise AssertionError(f"Unexpected response model: {response_model}")


def test_pipeline_runs_end_to_end_with_grounded_report(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mocked by parse_pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text(
        "Evaluate SoccerNet mAP 72.4 with python evaluate.py",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(
                page=1,
                text="The method reaches 72.4 mAP on SoccerNet.",
            )
        ],
    )

    report = analyze(paper_path, repository, PipelineLLMClient())

    assert len(report.claims) == 1
    assert report.claims[0].paper_evidence_validation[0].is_valid
    assert report.claims[0].retrieved_documents == ["README.md"]
    assert report.claims[0].mapping.status == "SUPPORTED"
    assert report.claims[0].mapping_evidence_validation[0].is_valid
    metric_item = next(
        item
        for item in report.claims[0].audit
        if item.check == "evaluation_protocol_metric"
    )
    assert metric_item.status == "PRESENT"

    json_path, markdown_path = write_analysis_report(report, tmp_path / "output")
    assert '"is_valid": true' in json_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "**VALID**" in markdown
    assert "**evaluation_protocol_metric: PRESENT**" in markdown
