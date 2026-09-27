# Paper2Repro

Paper2Repro is a small research prototype for auditing whether a machine learning paper's experimental claims can be connected to evidence in its official repository.

## Why this problem?

Reproducing a reported result often requires details spread across a paper, configuration files, scripts, checkpoints, and environment descriptions. Paper2Repro aims to make those connections easier to inspect.

## What Paper2Repro does

The current code provides repository file inventory, selectable-text extraction from local PDFs, and Gemini structured extraction of experimental claims. Extracted claims retain page-numbered paper excerpts that can be checked against the supplied page text.

## Architecture

- `models.py`: paper chunks, experimental claims, and repository artifacts.
- `repo/inventory.py`: classifies repository files into broad artifact types.
- `pdf.py`: converts each PDF page into a `PaperChunk`.
- `llm.py` and `providers/gemini.py`: provider interface and Gemini structured-output implementation.
- `claims/extractor.py`: page-tagged paper text to structured experimental claims.
- `claims/evidence.py`: deterministic page and excerpt validation.
- `report.py`: small Markdown rendering scaffold.
- `api.py`: minimal FastAPI health endpoint and analysis placeholder.

## Current v0.1 scope

- Inventory files under a local repository directory.
- Extract selectable text and page numbers from a local PDF.
- Extract main quantitative experimental claims using Gemini structured output.
- Store paper evidence as page and excerpt, then validate page membership and excerpt text deterministically.
- Run a minimal HTTP API and render simple Markdown sections.

Repository evidence retrieval and claim-to-repository mapping, and reproducibility judgments are not implemented.

## Limitations

- Scanned PDFs are not OCR processed.
- Repository inventory classifies paths only; it does not inspect artifact contents or establish that evidence supports a claim.
- Gemini claim extraction requires a valid `PAPER2REPRO_API_KEY` and makes an external API call.
- Evidence validation checks page and excerpt text after whitespace normalization; it does not judge whether the excerpt semantically supports the claim.
- The analysis endpoint is a stub.

## Future work

- Connect claims to repository evidence with traceable references.
- Define and implement the reproducibility audit criteria.
- Evaluate claim extraction quality across a curated set of papers.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
export PAPER2REPRO_API_KEY="your-gemini-api-key"
# Optional model override; defaults to gemini-3.8-flash.
export PAPER2REPRO_MODEL="gemini-3.8-flash"
```

`Settings.from_env()` reads both variables from the process environment. `.env.example` documents them, but `.env` files are not loaded automatically.

## Usage

Inventory a repository from Python:

```python
from pathlib import Path
from paper2repro.repo.inventory import inventory_repository

artifacts = inventory_repository(Path("/path/to/repository"))
```

Extract PDF text from Python:

```python
from pathlib import Path
from paper2repro.pdf import parse_pdf

chunks = parse_pdf(Path("paper.pdf"))
```

Extract and validate experimental claims:

```python
from paper2repro.claims.evidence import validate_evidence
from paper2repro.claims.extractor import extract_claims
from paper2repro.config import Settings
from paper2repro.pdf import parse_pdf
from paper2repro.providers.gemini import GeminiClient

chunks = parse_pdf(Path("paper.pdf"))
claims = extract_claims(chunks, GeminiClient(Settings.from_env()))
validation = validate_evidence(chunks, claims)
```

The manual integration check uses a short synthetic paper passage and skips when no API key is set:

```bash
uv run python scripts/manual_gemini_claim_extraction.py
```

The Gemini SDK uses JSON Schema structured output derived from the requested Pydantic model. Each claim contains one or more page-numbered excerpts; deterministic validation reports missing pages and excerpts without deleting claims.

Run the API and check its health endpoint:

```bash
uv run uvicorn paper2repro.api:app --reload
```

Open `http://127.0.0.1:8000/health`. `POST /analysis` currently returns a not-implemented placeholder.

Run the test suite:

```bash
uv run pytest
```
