"""Run the end-to-end Paper2Repro v0.1 analysis pipeline."""

import argparse
from collections import Counter
from pathlib import Path
import sys

from paper2repro.config import Settings
from paper2repro.observability import LLMCallBudgetExceeded
from paper2repro.pipeline import ClaimSourceError, analyze
from paper2repro.providers.gemini import GeminiClient, GeminiProviderError
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
    parser.add_argument(
        "--retriever",
        choices=("baseline", "weighted"),
        default="baseline",
        help="lexical repository retriever (default: baseline)",
    )
    parser.add_argument(
        "--reuse-claims-from",
        type=Path,
        help="reuse claims from an existing report.json without claim extraction",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        help="Optional maximum number of provider requests; the default is unlimited.",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path(".paper2repro_cache")
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable local response caching."
    )
    args = parser.parse_args()

    paper_path = args.paper.expanduser()
    if not paper_path.is_file():
        parser.error(f"PDF file does not exist or is not a file: {paper_path}")
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if args.max_llm_calls is not None and args.max_llm_calls < 1:
        parser.error("--max-llm-calls must be at least 1")
    reuse_claims_from = (
        args.reuse_claims_from.expanduser()
        if args.reuse_claims_from is not None
        else None
    )
    if reuse_claims_from is not None and not reuse_claims_from.is_file():
        parser.error(
            "Claim source report does not exist or is not a file: "
            f"{reuse_claims_from}"
        )

    settings = Settings.from_env()
    if not settings.api_key:
        parser.error("PAPER2REPRO_API_KEY is not set in the environment.")

    try:
        report = analyze(
            paper_path,
            args.repo,
            GeminiClient(settings),
            top_k=args.top_k,
            retriever=args.retriever,
            reuse_claims_from=reuse_claims_from,
            model_name=settings.model,
            cache_dir=None if args.no_cache else args.cache_dir,
            max_llm_calls=args.max_llm_calls,
            progress=lambda message: print(message, flush=True),
        )
    except GeminiProviderError as error:
        cache_note = (
            "Successful earlier results are cached and can be reused; rerun the same "
            "command after the provider issue clears."
            if not args.no_cache
            else "Rerun the command after the provider issue clears."
        )
        print(
            f"{error.provider} error (category: {error.category}):\n"
            + (
                f"code {error.provider_code}: "
                if error.provider_code is not None
                else ""
            )
            + (
                error.provider_message
                if error.provider_message
                else "No safe provider message was available."
            )
            + f"\nNo automatic retry was attempted. {cache_note}",
            file=sys.stderr,
        )
        return 1
    except LLMCallBudgetExceeded as error:
        cache_note = (
            f"Successful earlier responses are cached at {args.cache_dir}. "
            "Rerun with a higher --max-llm-calls value."
            if not args.no_cache
            else "No responses were cached because --no-cache was set. "
            "Rerun with a higher --max-llm-calls value."
        )
        print(
            f"LLM call budget reached: {error} {cache_note}",
            file=sys.stderr,
        )
        return 1
    except RepositorySourceError as error:
        parser.error(str(error))
    except ClaimSourceError as error:
        parser.error(str(error))

    print("[6/6] Writing reports...", flush=True)
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
        f"LLM requests: {report.performance.llm_request_count}; "
        f"cache hits: {report.performance.cache_hits}; "
        f"cache misses: {report.performance.cache_misses}"
    )
    print(
        "Elapsed: "
        f"total={report.performance.total_elapsed_seconds:.2f}s "
        f"pdf={report.performance.pdf_parsing_seconds:.2f}s "
        f"extraction={report.performance.claim_extraction_seconds:.2f}s "
        f"repository={report.performance.repository_preparation_seconds:.2f}s "
        f"inventory/loading={report.performance.inventory_loading_seconds:.2f}s "
        f"retrieval={report.performance.retrieval_seconds_total:.2f}s "
        f"report={report.performance.report_generation_seconds:.2f}s"
    )
    print(
        "Prompt/response characters: "
        f"{report.performance.prompt_characters_total}/"
        f"{report.performance.response_characters_total} "
        "(text lengths, not token or billing counts)"
    )
    for index, request in enumerate(report.performance.llm_requests, start=1):
        print(
            f"  LLM request {index}: {request.response_model}, "
            f"prompt={request.prompt_characters} chars, "
            f"response={request.response_characters} chars, "
            f"{request.elapsed_seconds:.2f}s"
        )
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
