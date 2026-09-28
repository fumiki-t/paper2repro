import re

from paper2repro.models import ExperimentalClaim, RepoDocument


def score_document(
    claim: ExperimentalClaim,
    document: RepoDocument,
) -> int:
    text = f"{document.path} {document.content}".lower()

    terms = []

    if claim.dataset:
        terms.append(claim.dataset.lower())

    if claim.metric:
        terms.append(claim.metric.lower())

    if claim.reported_value:
        terms.append(claim.reported_value.lower())

    score = 0

    for term in terms:
        if term in text:
            score += 1

    return score


def retrieve_documents(
    claim: ExperimentalClaim,
    documents: list[RepoDocument],
    top_k: int = 5,
) -> list[RepoDocument]:
    scored_documents = [
        (doc, score_document(claim, doc))
        for doc in documents
    ]

    scored_documents = [
        (doc, score)
        for doc, score in scored_documents
        if score > 0
    ]

    scored_documents.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    return [doc for doc, _ in scored_documents[:top_k]]


STOPWORDS = {
    "the",
    "a",
    "an",
    "on",
    "of",
    "and",
    "or",
    "to",
    "for",
    "with",
    "using",
    "by",
    "in",
    "at",
    "from",
    "than",
    "achieves",
    "achieve",
    "obtains",
    "obtain",
    "compared",
    "versus",
    "vs",
}


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def _tokenize(text: str) -> list[str]:
    """Split text into simple lowercase alphanumeric tokens."""
    return _TOKEN_PATTERN.findall(text.lower())


def _normalize_phrase(text: str) -> str:
    """Normalize punctuation-separated text into space-separated tokens."""
    return " ".join(_tokenize(text))


def _is_number(token: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d+)?", token) is not None


def build_query_terms(
    claim: ExperimentalClaim,
) -> list[tuple[str, int]]:
    """Build weighted lexical query terms from a claim."""
    term_weights: dict[str, int] = {}

    def add_term(term: str, weight: int) -> None:
        normalized = _normalize_phrase(term)

        if not normalized:
            return

        term_weights[normalized] = max(
            term_weights.get(normalized, 0),
            weight,
        )

    if claim.dataset:
        add_term(claim.dataset, 4)

        for token in _tokenize(claim.dataset):
            if token not in STOPWORDS and len(token) >= 2:
                add_term(token, 2)

    if claim.metric:
        add_term(claim.metric, 3)

        for token in _tokenize(claim.metric):
            if token not in STOPWORDS and len(token) >= 2:
                add_term(token, 2)

    if claim.reported_value:
        add_term(claim.reported_value, 2)

    for token in _tokenize(claim.statement):
        if token in STOPWORDS:
            continue

        if _is_number(token):
            continue

        if len(token) < 3:
            continue

        add_term(token, 1)

    return list(term_weights.items())


def _matches_term(
    term: str,
    normalized_text: str,
    tokens: set[str],
) -> bool:
    """Match phrases as substrings and single terms as exact tokens."""
    if " " in term:
        return term in normalized_text

    return term in tokens


def score_document_weighted(
    claim: ExperimentalClaim,
    document: RepoDocument,
) -> int:
    terms = build_query_terms(claim)

    normalized_path = _normalize_phrase(document.path)
    normalized_content = _normalize_phrase(document.content)

    path_tokens = set(normalized_path.split())
    content_tokens = set(normalized_content.split())

    score = 0

    for term, weight in terms:
        if _matches_term(
            term,
            normalized_path,
            path_tokens,
        ):

            score += weight + 1

        elif _matches_term(
            term,
            normalized_content,
            content_tokens,
        ):
            score += weight

    return score


def retrieve_documents_weighted(
    claim: ExperimentalClaim,
    documents: list[RepoDocument],
    top_k: int = 5,
) -> list[RepoDocument]:
    scored_documents = [
        (doc, score_document_weighted(claim, doc))
        for doc in documents
    ]

    scored_documents = [
        (doc, score)
        for doc, score in scored_documents
        if score > 0
    ]

    scored_documents.sort(
        key=lambda x: (-x[1], x[0].path)
    )

    return [
        doc
        for doc, _ in scored_documents[:top_k]
    ]
