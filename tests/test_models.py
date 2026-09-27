from paper2repro.models import (
    ClaimExtractionResult,
    ExperimentalClaim,
    PaperChunk,
    PaperEvidence,
    RepoArtifact,
)


def test_paper_chunk_keeps_text_and_page() -> None:
    chunk = PaperChunk(text="Experiment details", page=2)

    assert chunk.text == "Experiment details"
    assert chunk.page == 2


def test_experimental_claim_accepts_statement_and_evidence() -> None:
    claim = ExperimentalClaim(
        statement="Method A achieves 72.4 mIoU",
        evidence=[PaperEvidence(page=4, excerpt="Method A achieves 72.4 mIoU.")],
    )

    assert claim.statement == "Method A achieves 72.4 mIoU"
    assert claim.evidence[0].page == 4
    assert claim.dataset is None
    assert claim.metric is None
    assert claim.reported_value is None


def test_claim_result_validates_nested_models_and_multiple_evidence() -> None:
    result = ClaimExtractionResult.model_validate(
        {
            "claims": [
                {
                    "statement": "Method A outperforms baseline B",
                    "dataset": "Cityscapes",
                    "metric": "mIoU",
                    "reported_value": "72.4",
                    "evidence": [
                        {"page": 4, "excerpt": "Method A achieves 72.4 mIoU."},
                        {"page": 5, "excerpt": "This is 2.1 points above baseline B."},
                    ],
                }
            ]
        }
    )

    assert isinstance(result.claims[0], ExperimentalClaim)
    assert all(isinstance(item, PaperEvidence) for item in result.claims[0].evidence)
    assert len(result.claims[0].evidence) == 2


def test_repo_artifact_accepts_path_and_type() -> None:
    artifact = RepoArtifact(path="configs/run.yaml", artifact_type="config")

    assert artifact.path == "configs/run.yaml"
    assert artifact.artifact_type == "config"
