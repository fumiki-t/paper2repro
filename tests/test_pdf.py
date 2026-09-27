from pathlib import Path

from pypdf import PdfWriter

from paper2repro.pdf import parse_pdf


def test_parse_pdf_returns_one_based_page_chunks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)

    chunks = parse_pdf(pdf_path)

    assert [(chunk.page, chunk.text) for chunk in chunks] == [(1, ""), (2, "")]
