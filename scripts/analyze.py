"""Run the end-to-end Paper2Repro v0.1 analysis pipeline."""

import argparse
from collections import Counter
from pathlib import Path

from paper2repro.config import Settings
from paper2repro.pipeline import analyze
from paper2repro.providers.gemini import GeminiClient
from paper2repro.report import write_analysis_report
from paper2repro.repo.source import RepositorySourceError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a paper claim-by-claim against a repository."
    )
    parser.add_argument("--paper", required=True, type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/latest"))
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    paper_path = args.paper.expanduser()
    if not paper_path.is_file():
        parser.error(f"PDF file does not exist or is not a file: {paper_path}")
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    settings = Settings.from_env()
    if not settings.api_key:
        parser.error("PAPER2REPRO_API_KEY is not set in the environment.")

    try:
        report = analyze(
            paper_path,
            args.repo,
            GeminiClient(settings),
            top_k=args.top_k,
        )
    except RepositorySourceError as error:
        parser.error(str(error))

    json_path, markdown_path = write_analysis_report(report, args.output)
    paper_checks = [
        check
        for claim in report.claims
        for check in claim.paper_evidence_validation
    ]
    mapped_claims = sum(
        claim.mapping.status != "UNSUPPORTED" for claim in report.claims
    )
    audit_counts = Counter(
        item.status for claim in report.claims for item in claim.audit
    )

    print(f"Claims: {len(report.claims)}")
    print(
        "Valid paper evidence: "
        f"{sum(check.is_valid for check in paper_checks)} / {len(paper_checks)}"
    )
    print(f"Mapped claims: {mapped_claims} / {len(report.claims)}")
    print(
        "Audit: "
        f"PRESENT={audit_counts['PRESENT']} "
        f"AMBIGUOUS={audit_counts['AMBIGUOUS']} "
        f"NOT_FOUND={audit_counts['NOT_FOUND']}"
    )
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
