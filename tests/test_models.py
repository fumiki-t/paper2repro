from paper2repro.models import ExperimentalClaim, PaperChunk, RepoArtifact


def test_paper_chunk_keeps_text_and_page() -> None:
    chunk = PaperChunk(text="Experiment details", page=2)

    assert chunk.text == "Experiment details"
    assert chunk.page == 2


def test_experimental_claim_accepts_statement_and_page() -> None:
    claim = ExperimentalClaim(statement="Method A improves accuracy", page=4)

    assert claim.statement == "Method A improves accuracy"
    assert claim.page == 4


def test_repo_artifact_accepts_path_and_type() -> None:
    artifact = RepoArtifact(path="configs/run.yaml", artifact_type="config")

    assert artifact.path == "configs/run.yaml"
    assert artifact.artifact_type == "config"
