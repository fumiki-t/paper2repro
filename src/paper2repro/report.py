"""Markdown report rendering scaffold."""

from collections import Counter
from pathlib import Path
from time import perf_counter

from paper2repro.models import AnalysisReport, RepoEvidenceCheck


def render_markdown_report(title: str, sections: dict[str, str]) -> str:
    """Render named report sections as Markdown.

    ``sections`` can later be populated from an analysis report model. This
    renderer does not perform analysis or make audit judgments.
    """
    parts = [f"# {title}"]
    for heading, body in sections.items():
        parts.extend((f"## {heading}", body))
    return "\n\n".join(parts) + "\n"


def _validation_label(is_valid: bool) -> str:
    return "VALID" if is_valid else "INVALID"


def _duration(seconds: float | None) -> str:
    return "not recorded" if seconds is None else f"{seconds:.3f}s"


def _count(value: int | None) -> str:
    return "not recorded" if value is None else str(value)


def _repo_evidence_markdown(
    checks: list[RepoEvidenceCheck],
) -> list[str]:
    if not checks:
        return ["- No repository evidence was returned."]
    return [
        (
            f"- **{_validation_label(check.is_valid)}** `{check.path}`: "
            f'“{check.excerpt}”'
            + (f" ({check.reason})" if check.reason else "")
        )
        for check in checks
    ]


def render_analysis_report(report: AnalysisReport) -> str:
    """Render a traceable Markdown view of the structured analysis report."""
    paper_checks = [
        check for claim in report.claims for check in claim.paper_evidence_validation
    ]
    mapping_counts = Counter(claim.mapping.status for claim in report.claims)
    audit_counts = Counter(
        item.status for claim in report.claims for item in claim.audit
    )
    lines = [
        "# Paper2Repro analysis",
        "",
        "## Inputs",
        "",
        f"- Paper: `{report.paper}`",
        f"- Repository: `{report.repository}`",
        f"- Repository artifacts inventoried: {report.repository_artifact_count}",
        f"- Text documents loaded: {report.repository_document_count}",
        "",
        "## Summary",
        "",
        f"- Claims: {len(report.claims)}",
        "- Paper evidence anchored: "
        f"{sum(check.is_valid for check in paper_checks)} / {len(paper_checks)}",
        "- Mapping: "
        f"SUPPORTED={mapping_counts['SUPPORTED']}, "
        f"PARTIALLY_SUPPORTED={mapping_counts['PARTIALLY_SUPPORTED']}, "
        f"UNSUPPORTED={mapping_counts['UNSUPPORTED']}",
        "- Repository audit: "
        f"PRESENT={audit_counts['PRESENT']}, AMBIGUOUS={audit_counts['AMBIGUOUS']}, "
        f"NOT_FOUND={audit_counts['NOT_FOUND']}",
        "",
        "| # | Claim | Dataset | Metric / value | Paper evidence | Mapping |",
        "|---:|---|---|---|---:|---|",
    ]

    for claim_index, analysis in enumerate(report.claims, start=1):
        statement = analysis.claim.statement.replace("|", "\\|").replace("\n", " ")
        if len(statement) > 120:
            statement = statement[:117].rstrip() + "..."
        valid = sum(item.is_valid for item in analysis.paper_evidence_validation)
        total = len(analysis.paper_evidence_validation)
        metric_value = analysis.claim.metric or "unknown"
        if analysis.claim.reported_value:
            metric_value += f" {analysis.claim.reported_value}"
        lines.append(
            f"| {claim_index} | {statement} | {analysis.claim.dataset or 'unknown'} | "
            f"{metric_value} | {valid}/{total} | {analysis.mapping.status} |"
        )

    lines.extend(
        [
            "",
            "`NOT_FOUND` applies only to the repository artifacts retrieved and inspected "
            "for that claim. It does not establish repository-wide absence.",
        ]
    )

    for claim_index, analysis in enumerate(report.claims, start=1):
        claim = analysis.claim
        lines.extend(
            [
                "",
                f"## Claim {claim_index}",
                "",
                claim.statement,
                "",
                f"- Dataset: {claim.dataset or 'unknown'}",
                f"- Metric: {claim.metric or 'unknown'}",
                f"- Reported value: {claim.reported_value or 'unknown'}",
                "",
                "### Paper evidence",
                "",
            ]
        )
        if analysis.paper_evidence_validation:
            for check in analysis.paper_evidence_validation:
                suffix = f" ({check.reason})" if check.reason else ""
                lines.append(
                    f"- **{_validation_label(check.is_valid)}**, page {check.page}: "
                    f'“{check.excerpt}”{suffix}'
                )
        else:
            lines.append("- No paper evidence was returned.")

        lines.extend(["", "### Retrieved repository documents", ""])
        lines.extend(
            [f"- `{path}`" for path in analysis.retrieved_documents]
            or ["- No documents matched the lexical retrieval terms."]
        )
        if not analysis.retrieved_documents:
            lines.extend(
                [
                    "",
                    "**Retrieval returned no documents for this claim.** Any `NOT_FOUND` "
                    "audit items here describe an empty inspected set, not repository-wide absence.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Audit statuses apply only to the retrieved documents listed above; "
                    "`NOT_FOUND` does not prove repository-wide absence.",
                ]
            )
        lines.extend(
            [
                "",
                "### Claim to repository mapping",
                "",
                f"- Status: **{analysis.mapping.status}**",
                f"- Explanation: {analysis.mapping.explanation}",
            ]
        )
        lines.extend(_repo_evidence_markdown(analysis.mapping_evidence_validation))
        audit_checks = {
            group.check: group.evidence
            for group in analysis.audit_evidence_validation
        }
        lines.extend(["", "### Reproduction checklist", ""])
        for item in analysis.audit:
            lines.append(f"- **{item.check}: {item.status}** — {item.notes}")
            lines.extend(_repo_evidence_markdown(audit_checks.get(item.check, [])))

        if analysis.warnings:
            lines.extend(["", "### Claim warnings", ""])
            lines.extend(f"- {warning}" for warning in analysis.warnings)

    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report.warnings)
    if not report.warnings:
        lines.append("- No validation warnings.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    performance = report.performance
    lines.extend(
        [
            "",
            "## Runtime measurements",
            "",
            f"- Total elapsed: {_duration(performance.total_elapsed_seconds)}",
            f"- PDF parsing: {_duration(performance.pdf_parsing_seconds)}",
            f"- Claim extraction: {_duration(performance.claim_extraction_seconds)}",
            "- Repository preparation: "
            f"{_duration(performance.repository_preparation_seconds)}",
            "- Inventory and loading: "
            f"{_duration(performance.inventory_loading_seconds)}",
            f"- Retrieval total: {_duration(performance.retrieval_seconds_total)}",
            f"- Report generation: {_duration(performance.report_generation_seconds)}",
            f"- LLM requests: {_count(performance.llm_request_count)}; "
            f"cache hits: {_count(performance.cache_hits)}",
            f"- Prompt characters: {_count(performance.prompt_characters_total)}; "
            f"response characters: {_count(performance.response_characters_total)}",
            "- Character counts are text lengths, not token counts or billing measurements.",
        ]
    )
    if performance.claims:
        lines.extend(
            [
                "",
                "| Claim | Retrieval | Mapping / audit | Total | Cache hit |",
                "|---:|---:|---:|---:|:---:|",
            ]
        )
        for timing in performance.claims:
            lines.append(
                f"| {timing.claim_index} | {timing.retrieval_seconds:.3f}s | "
                f"{timing.mapping_audit_seconds:.3f}s | {timing.total_seconds:.3f}s | "
                f"{'yes' if timing.cache_hit else 'no'} |"
            )
    return "\n".join(lines) + "\n"


def write_analysis_report(
    report: AnalysisReport, output_dir: Path
) -> tuple[Path, Path]:
    """Write machine-readable JSON and human-readable Markdown reports."""
    started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    pipeline_elapsed = report.performance.total_elapsed_seconds
    markdown = render_analysis_report(report)
    report.performance.report_generation_seconds = perf_counter() - started
    report.performance.total_elapsed_seconds = (
        pipeline_elapsed + report.performance.report_generation_seconds
        if pipeline_elapsed is not None
        else None
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    report.performance.report_generation_seconds = perf_counter() - started
    report.performance.total_elapsed_seconds = (
        pipeline_elapsed + report.performance.report_generation_seconds
        if pipeline_elapsed is not None
        else None
    )
    markdown_path.write_text(render_analysis_report(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return json_path, markdown_path
