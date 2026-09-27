"""Prompt construction for experimental claim extraction."""

from paper2repro.models import PaperChunk


def build_claim_extraction_prompt(chunks: list[PaperChunk]) -> str:
    """Format page-tagged paper text and extraction instructions."""
    paper_text = "\n\n".join(
        f"[PAGE {chunk.page}]\n{chunk.text}" for chunk in chunks
    )
    return f"""Extract only the main experimental results that could be targets for reproduction.

Prioritize quantitative dataset performance, benchmark results, comparisons with
baselines, ablations, and other reported experimental outcomes. Do not turn every
number into a claim. Exclude research goals, background, related work, and method
novelty statements without an experimental result.

Keep claims atomic: one ExperimentalClaim should normally represent one
reproducible quantitative result with one primary metric and reported value. Split
results for different tasks or metrics into separate claims. A comparison using
the same metric, such as a method score versus a baseline score, may remain one
claim.

For every claim, include one or more evidence items. Each evidence excerpt must be
a short, verbatim passage copied from the supplied paper text, and its page must
match the [PAGE n] marker. Never invent or paraphrase an excerpt. Do not emit a
claim if no supporting passage can be copied from the input. Do not infer missing
dataset, metric, or reported value; use null when the paper does not state it.

Paper text:
{paper_text}"""
