"""Extract claims from a local PDF and validate their paper evidence."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from paper2repro.claims.evidence import validate_evidence
from paper2repro.claims.extractor import extract_claims
from paper2repro.config import Settings
from paper2repro.pdf import parse_pdf
from paper2repro.providers.gemini import GeminiClient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract experimental claims from a local PDF using Gemini."
    )
    parser.add_argument("pdf", type=Path, help="path to a local paper PDF")
    args = parser.parse_args()

    pdf_path = args.pdf.expanduser()
    if not pdf_path.is_file():
        parser.error(f"PDF file does not exist or is not a file: {pdf_path}")

    settings = Settings.from_env()
    if not settings.api_key:
        parser.error("PAPER2REPRO_API_KEY is not set in the environment.")

    chunks = parse_pdf(pdf_path)
    result = extract_claims(chunks, GeminiClient(settings))
    validations = validate_evidence(chunks, result)

    print("Claim extraction result:")
    print(result.model_dump_json(indent=2))
    print("Evidence validation result:")
    print(json.dumps([asdict(item) for item in validations], indent=2))

    evidence_count = sum(len(claim.evidence) for claim in result.claims)
    valid_evidence_count = sum(item.is_valid for item in validations)
    print(f"Claims: {len(result.claims)}")
    print(f"Valid evidence: {valid_evidence_count} / {evidence_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
