from paper2repro.models import ExperimentalClaim, RepoDocument
from paper2repro.retrieval.keyword import retrieve_documents, score_document


def _claim() -> ExperimentalClaim:
    return ExperimentalClaim(
        statement="The model reaches 72.4 mIoU on Cityscapes.",
        evidence=[],
        dataset="Cityscapes",
        metric="mIoU",
        reported_value="72.4",
    )


def _document(path: str, content: str) -> RepoDocument:
    return RepoDocument(path=path, artifact_type="config", content=content)


def test_score_document_matches_dataset_metric_and_value() -> None:
    claim = _claim()

    assert score_document(claim, _document("a.txt", "Cityscapes")) == 1
    assert score_document(claim, _document("a.txt", "mIoU")) == 1
    assert score_document(claim, _document("a.txt", "72.4")) == 1
    assert score_document(claim, _document("a.txt", "Cityscapes mIoU 72.4")) == 3


def test_score_document_matches_path_case_insensitively() -> None:
    assert score_document(_claim(), _document("configs/CITYSCAPES.yaml", "")) == 1


def test_retrieve_documents_excludes_zero_and_applies_top_k() -> None:
    documents = [
        _document("best.txt", "Cityscapes mIoU 72.4"),
        _document("second.txt", "Cityscapes mIoU"),
        _document("third.txt", "72.4"),
        _document("none.txt", "unrelated"),
    ]

    retrieved = retrieve_documents(_claim(), documents, top_k=2)

    assert [document.path for document in retrieved] == ["best.txt", "second.txt"]
