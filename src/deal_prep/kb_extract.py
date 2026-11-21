"""Format-specific extraction for the v1 knowledge base.

Supported: .md, .txt, .docx, text-based .pdf, simple .xlsx (first row = header, no merged
cells, no formulas). Scanned/OCR PDFs and complex spreadsheets raise UnsupportedFormatError.
Each table row becomes its own block with headers repeated ("Product: X | Price: Y"), so a
product stays associated with its own price. Blocks carry a location (page/sheet/row).
"""
from pathlib import Path

from deal_prep.chunking import _blocks, _is_separator, _split_row
from deal_prep.corpus import UnsupportedFormatError

SUPPORTED_FORMATS = {"md", "txt", "docx", "xlsx", "pdf"}


def _block(kind, section, text, location=""):
    return {"kind": kind, "section": section, "text": text, "location": location}


def _row_text(header, cells):
    return " | ".join(f"{h}: {c}" for h, c in zip(header, cells))


def _text_blocks(text):
    out = []
    for section, kind, payload in _blocks(text):
        if kind == "paragraph":
            out.append(_block("paragraph", section, payload))
            continue
        header, n = _split_row(payload[0]), 0
        for line in payload[1:]:
            if not _is_separator(line):
                n += 1
                out.append(_block("table_row", section, _row_text(header, _split_row(line)), f"row {n}"))
    return out


def _docx_blocks(path):
    import docx
    from docx.table import Table

    section, out = "", []
    for item in docx.Document(str(path)).iter_inner_content():
        if isinstance(item, Table):
            rows = [[c.text.strip() for c in r.cells] for r in item.rows]
            for i, cells in enumerate(rows[1:], 1):
                out.append(_block("table_row", section, _row_text(rows[0], cells), f"table row {i}"))
            continue
        text = item.text.strip()
        if not text:
            continue
        if item.style.name.startswith("Heading") or item.style.name == "Title":
            section = text
        else:
            out.append(_block("paragraph", section, text))
    return out


def _xlsx_blocks(path):
    import openpyxl

    out = []
    for ws in openpyxl.load_workbook(path, data_only=False).worksheets:
        if ws.merged_cells.ranges:
            raise UnsupportedFormatError(f"{path.name}: merged cells (complex spreadsheet) are not supported")
        rows = []
        for r in ws.iter_rows():
            if any(c.data_type == "f" for c in r):
                raise UnsupportedFormatError(f"{path.name}: formulas (complex spreadsheet) are not supported")
            values = ["" if c.value is None else str(c.value).strip() for c in r]
            if any(values):
                rows.append((r[0].row, values))
        if not rows:
            continue
        if ws.max_column == 1:
            out += [_block("paragraph", ws.title, v[0], f"sheet {ws.title} row {n}") for n, v in rows]
        else:
            (_, header), *body = rows
            out += [_block("table_row", ws.title, _row_text(header, v), f"sheet {ws.title} row {n}") for n, v in body]
    return out


def _pdf_blocks(path):
    from pypdf import PdfReader

    out = []
    for i, page in enumerate(PdfReader(str(path)).pages, 1):
        lines = [ln.strip() for ln in (page.extract_text() or "").splitlines() if ln.strip()]
        if lines:
            out.append(_block("paragraph", lines[0], " ".join(lines), f"page {i}"))
    if not out:
        raise UnsupportedFormatError(f"{path.name}: no text layer (scanned/OCR PDFs are not supported)")
    return out


def extract(path: Path) -> tuple[str, list[dict]]:
    """Return (full_text, blocks). full_text includes banners and is what the validator checks."""
    file_type = path.suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f".{file_type} is not a supported format")
    if file_type in ("md", "txt"):
        text = path.read_text(encoding="utf-8")
        return text, _text_blocks(text)
    blocks = {"docx": _docx_blocks, "xlsx": _xlsx_blocks, "pdf": _pdf_blocks}[file_type](path)
    return "\n\n".join(b["text"] for b in blocks), blocks


def is_banner(text: str) -> bool:
    return text.lstrip("> ").startswith("SYNTHETIC")
