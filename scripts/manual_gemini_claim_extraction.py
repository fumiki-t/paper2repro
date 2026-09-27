"""Manual smoke test for Gemini claim extraction; requires PAPER2REPRO_API_KEY."""

import json
import os

from paper2repro.claims.evidence import validate_evidence
from paper2repro.claims.extractor import extract_claims
from paper2repro.config import Settings
from paper2repro.models import PaperChunk
from paper2repro.providers.gemini import GeminiClient


def main() -> int:
    if not os.getenv("PAPER2REPRO_API_KEY"):
        print("SKIP: set PAPER2REPRO_API_KEY to run the Gemini integration check.")
        return 0

    chunks = [
        PaperChunk(
            page=1,
            text=(
                "We evaluate our method on the Cityscapes validation benchmark. "
                "Our method achieves 72.4 mIoU, compared with 70.1 mIoU for the "
                "baseline. These results suggest that the proposed method is useful."
            ),
        )
    ]
    result = extract_claims(chunks, GeminiClient(Settings.from_env()))
    validations = validate_evidence(chunks, result)
    print(result.model_dump_json(indent=2))
    print(json.dumps([item.__dict__ for item in validations], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
