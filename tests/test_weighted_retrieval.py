from paper2repro.models import ExperimentalClaim, RepoDocument
from paper2repro.retrieval.keyword import (
    build_query_terms,
    retrieve_documents_weighted,
    score_document_weighted,
)


def _claim(
    *,
    statement: str = "",
    dataset: str | None = None,
    metric: str | None = None,
    reported_value: str | None = None,
) -> ExperimentalClaim:
    return ExperimentalClaim(
        statement=statement,
        evidence=[],
        dataset=dataset,
        metric=metric,
        reported_value=reported_value,
    )


def _document(path: str, content: str) -> RepoDocument:
    return RepoDocument(path=path, artifact_type="other", content=content)


def test_statement_terms_contribute_to_ranking() -> None:
    claim = _claim(
        statement="The lightweight decoder improves athlete detection.",
        dataset="SoccerNet",
        metric="mAP",
        reported_value="49.5",
    )
    generic = _document("a/generic.yaml", "SoccerNet mAP 49.5")
    statement_match = _document(
        "z/decoder.yaml", "SoccerNet mAP 49.5 lightweight decoder"
    )

    assert score_document_weighted(claim, statement_match) > score_document_weighted(
        claim, generic
    )
    assert retrieve_documents_weighted(claim, [generic, statement_match])[0] == (
        statement_match
    )


def test_stopwords_are_excluded_from_weighted_query_terms() -> None:
    claim = _claim(statement="the on using and for")

    assert build_query_terms(claim) == []
    assert retrieve_documents_weighted(
        claim, [_document("readme.md", "the on using and for")]
    ) == []


def test_dataset_metric_and_reported_value_keep_their_weights() -> None:
    claim = _claim(
        dataset="SoccerNet",
        metric="mAP",
        reported_value="49.5",
    )

    assert dict(build_query_terms(claim)) == {
        "soccernet": 4,
        "map": 3,
        "49.5": 2,
    }


def test_decimal_reported_value_does_not_match_a_larger_number() -> None:
    claim = _claim(reported_value="49.5")
    document = _document("metrics.txt", "unrelated coordinate 349.51")

    assert score_document_weighted(claim, document) == 0
    assert retrieve_documents_weighted(claim, [document]) == []


def test_path_match_scores_higher_than_body_match() -> None:
    claim = _claim(dataset="SoccerNet")
    path_match = _document("configs/SoccerNet.yaml", "evaluation config")
    body_match = _document("configs/evaluation.yaml", "dataset: SoccerNet")

    assert score_document_weighted(claim, path_match) == 5
    assert score_document_weighted(claim, body_match) == 4
    assert retrieve_documents_weighted(claim, [body_match, path_match])[0] == (
        path_match
    )


def test_equal_scores_are_ordered_by_path() -> None:
    claim = _claim(dataset="SoccerNet")
    later_path = _document("z/result.yaml", "dataset: SoccerNet")
    earlier_path = _document("a/result.yaml", "dataset: SoccerNet")

    ranked = retrieve_documents_weighted(claim, [later_path, earlier_path])

    assert [document.path for document in ranked] == [
        "a/result.yaml",
        "z/result.yaml",
    ]


def test_retriever_drops_zero_scores_and_honors_top_k() -> None:
    claim = _claim(dataset="SoccerNet")
    documents = [
        _document("b/result.yaml", "dataset: SoccerNet"),
        _document("none.yaml", "unrelated"),
        _document("a/result.yaml", "dataset: SoccerNet"),
    ]

    ranked = retrieve_documents_weighted(claim, documents, top_k=1)

    assert len(ranked) == 1
    assert ranked[0].path == "a/result.yaml"
    assert all(score_document_weighted(claim, doc) > 0 for doc in ranked)


def test_no_match_returns_no_documents() -> None:
    claim = _claim(dataset="SoccerNet")

    assert retrieve_documents_weighted(
        claim, [_document("readme.md", "unrelated project")]
    ) == []
