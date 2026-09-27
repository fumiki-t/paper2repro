# Paper2Repro v0.1 performance notes

## What the SoccerMaster development run tells us

The saved run reports 9 extracted claims, 740 inventoried artifacts, and 621 loaded text documents. Seven claims had at least one retrieved document and two had none. The current pipeline calls the LLM once for claim extraction, then once for each claim with non-empty retrieval: **1 + 7 = 8 sequential provider requests**. `assess_claim_repository()` skips the provider when retrieval is empty. The report contains no wall-clock or provider-request log, so elapsed-time figures for that earlier run cannot be recovered reliably.

## Likely latency contributors

1. **Provider round trips:** up to eight synchronous Gemini calls run serially. Network latency and provider queue time are likely to dominate when the repository is already local.
2. **Repository preparation:** a GitHub URL is shallow-cloned before analysis. Network and GitHub availability affect this stage; local repositories avoid the clone.
3. **PDF parsing:** pypdf extracts selectable text page by page. This is local CPU and file I/O; image-only pages are not OCR processed.
4. **Inventory and loading:** the inventory walks the repository, then the loader opens eligible text artifacts and enforces its size and type exclusions. The previous run loaded 621 documents from 740 artifacts.
5. **Retrieval:** the baseline scans each loaded document for each claim. It is simple but repeats work across claims. With 9 claims and 621 documents this is a bounded local scan, but larger repositories increase the work.
6. **Evidence validation and report rendering:** these are deterministic local string/path checks and Markdown/JSON formatting. They should be measured, but are not expected to cost as much as serial API round trips or cloning for this run.

The CLI and `report.json` now record stage timings, total time, per-claim retrieval and mapping/audit time, actual LLM request count, and per-request latency. If caching is enabled, cache hits and misses are recorded as well. Prompt and response character counts are plain text lengths; they are **not token counts and do not estimate billing**.

## Prompt size risk

`build_repository_assessment_prompt()` includes the full text of every retrieved `RepoDocument`. With `top_k=5`, one mapping request can therefore include five complete files, in addition to the claim and instructions. The loader currently permits a text file up to 256,000 bytes, so the loose upper bound from five maximum-sized files is about 1.28 MB of source bytes for one mapping prompt. Actual prompts are generally smaller, but no truncation or token-budget check currently limits them. Large READMEs/configs can increase latency or exceed provider request limits.

The current runtime instrumentation records character counts so actual prompt sizes can be observed. These counts are not tokenizer-aware. The v0.1 pipeline intentionally keeps whole-document prompts; do not treat a character count as a billing figure.

## Cache, budget, and request behavior

- The CLI uses `.paper2repro_cache/` by default. It is gitignored and can be changed with `--cache-dir` or disabled with `--no-cache`.
- Successful structured claim extraction and per-claim mapping/audit responses are written as inspectable JSON via a same-directory temporary file and atomic rename.
- Cache keys include the paper text hash or claim data, model, prompt/schema version, and for mapping the retrieval version, `top_k`, retrieved paths and content hashes. Bump the prompt/retrieval version constants when those behaviors change.
- Deterministic evidence validation still runs on every invocation, including cache hits.
- `--max-llm-calls N` blocks a request before it is sent if N provider requests have already been made. No cap applies by default. The client does not automatically retry rate limits.
- The Gemini SDK client is configured for one attempt per request so its transport does not silently retry 429 responses.
- A successful response is cached immediately before later work begins, so a later provider error or a budget stop can reuse completed responses.

## Possible future improvement

After a human-reviewed retrieval evaluation, split large files into bounded chunks with path and line/page provenance, retrieve the most relevant chunks, and pass only those excerpts to the mapping prompt. Keep the original file path available for evidence validation, and compare candidate retrieval against this lexical baseline before changing the default. This is a future design direction; chunking is not part of the current implementation.
