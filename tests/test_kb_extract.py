"""Five-format extraction for the v1 knowledge base (spec FR-03/FR-04, Decision 19)."""
import openpyxl
import pytest
from fpdf import FPDF

from deal_prep.corpus import UnsupportedFormatError
from deal_prep.kb_extract import extract
from deal_prep.provenance import KB_DIR

SYN = KB_DIR / "synthetic"


def _rows(blocks):
    return [b for b in blocks if b["kind"] == "table_row"]


def _fields(text):
    return dict(p.split(": ", 1) for p in text.split(" | "))


def test_xlsx_price_rows_keep_product_price_unit_and_term():
    _, blocks = extract(SYN / "NVQ-PRC-2026-v1_price_list_2026.xlsx")
    rows = {(_fields(b["text"])["Product"], _fields(b["text"])["Tier"]): _fields(b["text"]) for b in _rows(blocks)}
    assert rows[("Nivarque Core", "Business")]["List price (USD)"] == "34"
    assert rows[("Nivarque Engineering Vault", "Enterprise")]["List price (USD)"] == "52"
    assert rows[("Nivarque Engineering Vault", "Enterprise")]["Minimum term"] == "24 months"
    assert rows[("Records Retention Add-on", "Add-on")]["Unit"] == "per TB per month"
    assert len(rows) == 4


def test_xlsx_rows_carry_sheet_and_row_location():
    _, blocks = extract(SYN / "NVQ-PRC-2025-v1_price_list_2025.xlsx")
    business = next(b for b in _rows(blocks) if "Tier: Business" in b["text"])
    assert business["location"] == "sheet List prices row 3"
    assert "List price (USD): 30" in business["text"]
    notes = [b for b in blocks if b["section"] == "Notes"]
    assert any("Superseded by NVQ-PRC-2026-v1" in b["text"] for b in notes)


def test_docx_paragraphs_headings_and_table_rows():
    full, blocks = extract(SYN / "NVQ-PRP-002_arup_proposal.docx")
    assert "SYNTHETIC RECORD — fictional relationship with a real company." in full
    rows = _rows(blocks)
    vault = next(_fields(b["text"]) for b in rows if "Engineering Vault" in b["text"])
    assert vault["Proposed price (USD)"] == "46" and vault["Quantity"] == "1200"
    assert all(b["section"] == "Proposed pricing" for b in rows)
    assert any(b["section"] == "Commercial terms" and "does not change the list price" in b["text"] for b in blocks)


def test_pdf_text_extracted_per_page_with_location():
    full, blocks = extract(SYN / "NVQ-POL-001_commercial_policy.pdf")
    discount = next(b for b in blocks if b["section"] == "Discount approval policy")
    assert discount["location"] == "page 2"
    assert "above 25 percent require approval from the CFO" in discount["text"]
    assert full.startswith("SYNTHETIC - fictional vendor")


@pytest.mark.parametrize("name", ["NVQ-POL-002_security_faq.txt", "NVQ-CMP-001_battlecard_solquend.md"])
def test_text_formats_extract_paragraphs(name):
    _, blocks = extract(SYN / name)
    assert len(blocks) >= 3 and all(b["kind"] == "paragraph" for b in blocks)


def test_scanned_pdf_without_text_layer_rejected(tmp_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.rect(10, 10, 50, 50)  # an image-like page with no text
    path = tmp_path / "scanned.pdf"
    pdf.output(str(path))
    with pytest.raises(UnsupportedFormatError, match="scanned/OCR"):
        extract(path)


def test_xlsx_with_formula_rejected(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["Product", "Price"])
    wb.active.append(["X", "=1+1"])
    path = tmp_path / "formula.xlsx"
    wb.save(path)
    with pytest.raises(UnsupportedFormatError, match="formulas"):
        extract(path)


def test_xlsx_with_merged_cells_rejected(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["Product", "Price"])
    wb.active.merge_cells("A1:B1")
    path = tmp_path / "merged.xlsx"
    wb.save(path)
    with pytest.raises(UnsupportedFormatError, match="merged cells"):
        extract(path)


def test_unknown_format_rejected(tmp_path):
    path = tmp_path / "notes.pptx"
    path.write_bytes(b"x")
    with pytest.raises(UnsupportedFormatError):
        extract(path)
