from io import BytesIO

import pytest

from mnemos.services.document_extraction import ImageOnlyPdfError, chunk_sections, extract_document


def test_extracts_real_text_and_chunks_with_locator():
    sections = extract_document(
        b"Asset P-117 experienced recurring seal leakage.\nInspect alignment.",
        "text/plain",
        "pump.txt",
    )
    assert "P-117" in sections[0].text
    chunks = chunk_sections(sections)
    assert chunks[0][0].locator == "document"
    assert "seal leakage" in chunks[0][1]


def test_csv_preserves_headers_and_rows():
    sections = extract_document(
        b"asset,condition\nP-117,elevated vibration\n", "text/csv", "inspection.csv"
    )
    assert "asset | condition" in sections[0].text
    assert "asset=P-117" in sections[0].text


def test_image_only_pdf_is_not_marked_readable():
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(ImageOnlyPdfError):
        extract_document(stream.getvalue(), "application/pdf", "scan.pdf")
