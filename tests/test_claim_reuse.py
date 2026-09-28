from pathlib import Path

import pytest

from paper2repro.models import (
    ClaimExtractionResult,
    ClaimRepositoryAssessment,
    ClaimRepositoryMapping,
    ExperimentalClaim,
    PaperChunk,
    PaperEvidence,
    RepoEvidence,
)
from paper2repro.pipeline import ClaimSourceError, analyze
from paper2repro.report import write_analysis_report


def _nine_claims() -> list[ExperimentalClaim]:
    claims = []
    for index in range(1, 10):
        value = f"{50 + index}.0"
        excerpt = f"The model scores {value} mAP on SoccerNet."
        claims.append(
            ExperimentalClaim(
                statement=excerpt,
                evidence=[PaperEvidence(page=1, excerpt=excerpt)],
                dataset="SoccerNet",
                metric="mAP",
                reported_value=value,
            )
        )
    return claims


class NineClaimClient:
    def __init__(self) -> None:
        self.response_models: list[type] = []

    def generate_structured(self, prompt, response_model):
        self.response_models.append(response_model)
        if response_model is ClaimExtractionResult:
            return ClaimExtractionResult(claims=_nine_claims())
        if response_model is ClaimRepositoryAssessment:
            evidence = RepoEvidence(
                path="README.md",
                artifact_type="readme",
                excerpt="SoccerNet mAP",
            )
            return ClaimRepositoryAssessment(
                mapping=ClaimRepositoryMapping(
                    status="SUPPORTED",
                    evidence=[evidence],
                    explanation="The README records the dataset and metric.",
                ),
                audit=[],
            )
        raise AssertionError(f"Unexpected response model: {response_model}")


def _setup_analysis(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mock PDF")
    repository = tmp_path / "repository"
    repository.mkdir()
    values = [f"{50 + index}.0" for index in range(1, 10)]
    (repository / "README.md").write_text(
        "\n".join(f"SoccerNet mAP {value}" for value in values),
        encoding="utf-8",
    )
    paper_text = "\n".join(claim.statement for claim in _nine_claims())
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [PaperChunk(page=1, text=paper_text)],
    )
    return paper_path, repository


def test_reused_claims_skip_extraction_but_validate_and_map_all_nine(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path, repository = _setup_analysis(tmp_path, monkeypatch)
    client = NineClaimClient()

    original_report = analyze(paper_path, repository, client)
    assert client.response_models.count(ClaimExtractionResult) == 1
    assert client.response_models.count(ClaimRepositoryAssessment) == 9
    assert len(original_report.claims) == 9

    source_path = tmp_path / "baseline-report.json"
    source_path.write_text(
        original_report.model_dump_json(
            exclude={"claim_source", "claim_source_path"}
        ),
        encoding="utf-8",
    )
    client.response_models.clear()
    progress: list[str] = []

    reused_report = analyze(
        paper_path,
        repository,
        client,
        retriever="weighted",
        reuse_claims_from=source_path,
        max_llm_calls=9,
        progress=progress.append,
    )

    assert reused_report.claim_source == "reused_report"
    assert reused_report.claim_source_path == str(source_path)
    assert reused_report.claims == original_report.claims
    assert reused_report.performance.claim_extraction_seconds == 0.0
    assert reused_report.performance.llm_request_count == 9
    assert client.response_models == [ClaimRepositoryAssessment] * 9
    assert all(
        analysis.paper_evidence_validation[0].is_valid
        for analysis in reused_report.claims
    )
    assert all(
        analysis.mapping.status == "SUPPORTED" for analysis in reused_report.claims
    )
    assert any(
        message == f"[2/6] Reusing 9 experimental claims from {source_path}..."
        for message in progress
    )

    json_path, markdown_path = write_analysis_report(
        reused_report, tmp_path / "weighted-output"
    )
    assert '"claim_source": "reused_report"' in json_path.read_text(
        encoding="utf-8"
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "- Claim source: `reused_report`" in markdown
    assert f"- Claim source report: `{source_path}`" in markdown


def test_reuse_claims_rejects_missing_or_invalid_report(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path, repository = _setup_analysis(tmp_path, monkeypatch)
    client = NineClaimClient()
    missing_path = tmp_path / "missing-report.json"

    with pytest.raises(ClaimSourceError, match="does not exist or is not a file"):
        analyze(
            paper_path,
            repository,
            client,
            reuse_claims_from=missing_path,
        )

    invalid_path = tmp_path / "invalid-report.json"
    invalid_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ClaimSourceError, match="not valid Paper2Repro report JSON"):
        analyze(
            paper_path,
            repository,
            client,
            reuse_claims_from=invalid_path,
        )

    assert client.response_models == []
