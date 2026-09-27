from paper2repro.models import RepoDocument, RepoEvidence
from paper2repro.repo.evidence import validate_repo_evidence


def _document() -> RepoDocument:
    return RepoDocument(
        path="configs/eval.yaml",
        artifact_type="config",
        content="dataset: SoccerNet\nmetric: mAP\nscore: 72.4",
    )


def test_repo_evidence_validates_path_and_excerpt() -> None:
    evidence = RepoEvidence(
        path="configs/eval.yaml",
        artifact_type="config",
        excerpt="dataset: SoccerNet\nmetric: mAP",
    )

    [validation] = validate_repo_evidence([_document()], [evidence])

    assert validation.is_valid


def test_repo_evidence_rejects_unretrieved_path() -> None:
    evidence = RepoEvidence(
        path="invented.yaml",
        artifact_type="config",
        excerpt="dataset: SoccerNet",
    )

    [validation] = validate_repo_evidence([_document()], [evidence])

    assert not validation.is_valid
    assert validation.reason == "path_not_retrieved"


def test_repo_evidence_rejects_hallucinated_numeric_value() -> None:
    evidence = RepoEvidence(
        path="configs/eval.yaml",
        artifact_type="config",
        excerpt="score: 99.9",
    )

    [validation] = validate_repo_evidence([_document()], [evidence])

    assert not validation.is_valid
    assert validation.reason == "excerpt_not_found"
