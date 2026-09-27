"""Markdown report rendering scaffold."""

from pathlib import Path

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
    lines = [
        "# Paper2Repro analysis",
        "",
        "## Inputs",
        "",
        f"- Paper: `{report.paper}`",
        f"- Repository: `{report.repository}`",
        f"- Repository artifacts inventoried: {report.repository_artifact_count}",
        f"- Text documents loaded: {report.repository_document_count}",
    ]

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
    return "\n".join(lines) + "\n"


def write_analysis_report(
    report: AnalysisReport, output_dir: Path
) -> tuple[Path, Path]:
    """Write machine-readable JSON and human-readable Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_analysis_report(report), encoding="utf-8")
    return json_path, markdown_path
