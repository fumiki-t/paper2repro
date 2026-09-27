"""Inspect baseline lexical retrieval for an existing report without an LLM."""

import argparse
from pathlib import Path

from paper2repro.models import AnalysisReport
from paper2repro.repo.inventory import inventory_repository
from paper2repro.repo.loader import load_repository_documents
from paper2repro.repo.source import RepositorySourceError, repository_source
from paper2repro.retrieval.keyword import retrieve_documents, score_document


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Debug keyword retrieval from a report; this command never calls an LLM."
        )
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if not args.report.is_file():
        parser.error(f"Report JSON does not exist: {args.report}")

    try:
        report = AnalysisReport.model_validate_json(
            args.report.read_text(encoding="utf-8")
        )
        with repository_source(args.repo) as root:
            artifacts = inventory_repository(root)
            documents = load_repository_documents(root, artifacts)
            print(
                f"Loaded {len(documents)} text documents from {args.repo}; "
                "LLM calls: 0"
            )
            for index, analysis in enumerate(report.claims, start=1):
                claim = analysis.claim
                print(f"\nClaim {index}: {claim.statement}")
                print(
                    "Query fields: "
                    f"dataset={claim.dataset!r}, metric={claim.metric!r}, "
                    f"reported_value={claim.reported_value!r}"
                )
                scored = [
                    (document, score_document(claim, document))
                    for document in documents
                ]
                scored = [(doc, score) for doc, score in scored if score > 0]
                scored.sort(key=lambda pair: pair[1], reverse=True)
                top = retrieve_documents(claim, documents, top_k=args.top_k)
                if not top:
                    print("No retrieved documents (all scores were 0).")
                    continue
                scores_by_path = {document.path: score for document, score in scored}
                print(f"Top {len(top)} documents:")
                for document in top:
                    print(f"  score={scores_by_path[document.path]}  {document.path}")
    except (OSError, ValueError, RepositorySourceError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
