"""PDF text extraction helpers."""

from pathlib import Path

from pypdf import PdfReader

from paper2repro.models import PaperChunk


def parse_pdf(path: Path) -> list[PaperChunk]:
    """Extract selectable text from a local PDF, keeping 1-based page numbers."""
    reader = PdfReader(path)
    return [
        PaperChunk(text=page.extract_text() or "", page=page_number)
        for page_number, page in enumerate(reader.pages, start=1)
    ]
