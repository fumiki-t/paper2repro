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