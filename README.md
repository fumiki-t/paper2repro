# Paper2Repro

Paper2Repro is a small research prototype for auditing whether a machine learning paper's experimental claims can be connected to evidence in its official repository.

## Why this problem?

Reproducing a reported result often requires details spread across a paper, configuration files, scripts, checkpoints, and environment descriptions. Paper2Repro aims to make those connections easier to inspect.

## What Paper2Repro does

The current code provides basic data models, repository file inventory, and selectable-text extraction from local PDFs. It does not yet extract claims or assess whether a result is reproducible.

## Architecture

- `models.py`: paper chunks, experimental claims, and repository artifacts.
- `repo/inventory.py`: classifies repository files into broad artifact types.
- `pdf.py`: converts each PDF page into a `PaperChunk`.
- `llm.py`: provider-neutral interface for future Pydantic structured output.
- `report.py`: small Markdown rendering scaffold.
- `api.py`: minimal FastAPI health endpoint and analysis placeholder.

## Current v0.1 scope

- Inventory files under a local repository directory.
- Extract selectable text and page numbers from a local PDF.
- Run a minimal HTTP API and render simple Markdown sections.

Claim extraction, claim-to-repository evidence mapping, and reproducibility judgments are not implemented.

## Limitations

- Scanned PDFs are not OCR processed.
- Repository inventory classifies paths only; it does not inspect artifact contents or establish that evidence supports a claim.
- The LLM interface has no provider implementation and does not make API calls.
- The analysis endpoint is a stub.

## Future work

- Design and implement experimental claim extraction.
- Connect claims to repository evidence with traceable references.
- Define and implement the reproducibility audit criteria.
- Add a provider implementation behind the LLM interface.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env  # optional; set PAPER2REPRO_API_KEY when integrating a provider
```

`Settings.from_env()` can read `PAPER2REPRO_API_KEY` from the process environment. The current API and LLM interface do not consume it yet. No `.env` loader is enabled; export the variable in your shell or load the file with your preferred local tooling.

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

Run the API and check its health endpoint:

```bash
uv run uvicorn paper2repro.api:app --reload
```

Open `http://127.0.0.1:8000/health`. `POST /analysis` currently returns a not-implemented placeholder.

Run the test suite:

```bash
uv run pytest
```
