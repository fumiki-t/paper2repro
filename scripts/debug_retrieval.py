"""Compare baseline and weighted lexical retrieval without an LLM."""

import argparse
from pathlib import Path

from paper2repro.models import AnalysisReport, ExperimentalClaim, RepoDocument
from paper2repro.repo.inventory import inventory_repository
from paper2repro.repo.loader import load_repository_documents
from paper2repro.repo.source import RepositorySourceError, repository_source
from paper2repro.retrieval.keyword import (
    _matches_term,
    _normalize_phrase,
    build_query_terms,
    retrieve_documents,
    retrieve_documents_weighted,
    score_document,
    score_document_weighted,
)


def _matched_weighted_terms(
    claim: ExperimentalClaim, document: RepoDocument
) -> list[str]:
    terms = build_query_terms(claim)
    normalized_path = _normalize_phrase(document.path)
    normalized_content = _normalize_phrase(document.content)
    path_tokens = set(normalized_path.split())
    content_tokens = set(normalized_content.split())
    matched: list[str] = []

    for term, weight in terms:
        if _matches_term(term, normalized_path, path_tokens):
            matched.append(f"{term} (path +{weight + 1})")
        elif _matches_term(term, normalized_content, content_tokens):
            matched.append(f"{term} (body +{weight})")

    return matched


def _claim_indices(value: str) -> list[int]:
    try:
        indices = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "claim indices must be comma-separated positive integers"
        ) from error
    if not indices or any(index < 1 for index in indices):
        raise argparse.ArgumentTypeError(
            "claim indices must be comma-separated positive integers"
        )
    return list(dict.fromkeys(indices))


def _ranked_documents(
    retriever: str,
    claim: ExperimentalClaim,
    documents: list[RepoDocument],
    top_k: int,
) -> list[tuple[RepoDocument, int]]:
    if retriever == "baseline":
        ranked = retrieve_documents(claim, documents, top_k=top_k)
        scorer = score_document
    else:
        ranked = retrieve_documents_weighted(claim, documents, top_k=top_k)
        scorer = score_document_weighted
    return [(document, scorer(claim, document)) for document in ranked]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect lexical retrieval from a saved report; this command never "
            "calls an LLM. Use a local repository path for an offline run."
        )
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--retriever", choices=("baseline", "weighted"), default="baseline"
    )
    selection.add_argument(
        "--compare", action="store_true", help="show baseline and weighted rankings"
    )
    parser.add_argument(
        "--claims",
        type=_claim_indices,
        help="comma-separated 1-based claim numbers, for example 2,4,8,9",
    )
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not args.report.is_file():
        parser.error(f"Report JSON does not exist: {args.report}")

    try:
        report = AnalysisReport.model_validate_json(
            args.report.read_text(encoding="utf-8")
        )
        if args.claims:
            invalid = [index for index in args.claims if index > len(report.claims)]
            if invalid:
                parser.error(
                    f"Claim index out of range for this report: {', '.join(map(str, invalid))}"
                )
            selected = set(args.claims)
        else:
            selected = set(range(1, len(report.claims) + 1))

        with repository_source(args.repo) as root:
            artifacts = inventory_repository(root)
            documents = load_repository_documents(root, artifacts)
            print(
                f"Loaded {len(documents)} text documents from {args.repo}; "
                "LLM calls: 0"
            )
            for index, analysis in enumerate(report.claims, start=1):
                if index not in selected:
                    continue
                claim = analysis.claim
                print(f"\nClaim {index}: {claim.statement}")
                print(
                    "Query fields: "
                    f"dataset={claim.dataset!r}, metric={claim.metric!r}, "
                    f"reported_value={claim.reported_value!r}"
                )
                retrievers = (
                    ("baseline", "weighted")
                    if args.compare
                    else (args.retriever,)
                )
                for retriever in retrievers:
                    ranked = _ranked_documents(
                        retriever, claim, documents, top_k=args.top_k
                    )
                    label = "Baseline" if retriever == "baseline" else "Weighted"
                    print(f"{label} top-{len(ranked)}:")
                    if not ranked:
                        print("  No retrieved documents (all scores were 0).")
                        continue
                    for document, score in ranked:
                        print(f"  score={score}  {document.path}")
                        if retriever == "weighted":
                            matches = _matched_weighted_terms(claim, document)
                            print(
                                "    matched terms: "
                                + (", ".join(matches) if matches else "none")
                            )
    except (OSError, ValueError, RepositorySourceError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
