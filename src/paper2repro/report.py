"""Markdown report rendering scaffold."""


def render_markdown_report(title: str, sections: dict[str, str]) -> str:
    """Render named report sections as Markdown.

    ``sections`` can later be populated from an analysis report model. This
    renderer does not perform analysis or make audit judgments.
    """
    parts = [f"# {title}"]
    for heading, body in sections.items():
        parts.extend((f"## {heading}", body))
    return "\n\n".join(parts) + "\n"
