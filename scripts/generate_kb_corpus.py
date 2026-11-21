"""Generate the DOCX, XLSX and PDF documents of the v1 knowledge base deterministically.

Usage: python scripts/generate_kb_corpus.py
Writes into data/kb_v1/synthetic/. All content is synthetic (spec v1.2 §6B); the
matching metadata lives in data/kb_v1/manifest.json. MD/TXT documents are authored by hand.
"""
from datetime import datetime, timezone
from pathlib import Path

import docx
import openpyxl
from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "data" / "kb_v1" / "synthetic"
FIXED_TIME = datetime(2026, 11, 6, tzinfo=timezone.utc)
VENDOR_BANNER = "SYNTHETIC - fictional vendor. Nivarque Document Systems is a fictional company. Not a real business fact."
RELATIONSHIP_BANNER = "SYNTHETIC RECORD — fictional relationship with a real company. Not a real business fact."
PRICE_HEADER = ["Product", "Tier", "Unit", "List price (USD)", "Minimum term"]


def price_list(filename, title, rows, notes):
    wb = openpyxl.Workbook()
    wb.properties.created = wb.properties.modified = FIXED_TIME.replace(tzinfo=None)
    ws = wb.active
    ws.title = "List prices"
    ws.append(PRICE_HEADER)
    for row in rows:
        ws.append(row)
    notes_ws = wb.create_sheet("Notes")
    for line in [VENDOR_BANNER, title, *notes]:
        notes_ws.append([line])
    wb.save(OUT / filename)


def proposal(filename, title, sections, table_header, table_rows):
    d = docx.Document()
    d.core_properties.created = d.core_properties.modified = FIXED_TIME.replace(tzinfo=None)
    d.add_paragraph(RELATIONSHIP_BANNER)
    d.add_heading(title, level=1)
    for heading, paragraphs in sections:
        d.add_heading(heading, level=2)
        for p in paragraphs:
            d.add_paragraph(p)
    d.add_heading("Proposed pricing", level=2)
    table = d.add_table(rows=1, cols=len(table_header))
    for cell, text in zip(table.rows[0].cells, table_header):
        cell.text = text
    for row in table_rows:
        for cell, text in zip(table.add_row().cells, row):
            cell.text = text
    d.save(OUT / filename)


def policy_pdf(filename, pages):
    pdf = FPDF()
    pdf.set_creation_date(FIXED_TIME)
    pdf.set_font("Helvetica", size=11)
    for lines in pages:
        pdf.add_page()
        for line in lines:
            pdf.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
    pdf.output(str(OUT / filename))


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    price_list("NVQ-PRC-2025-v1_price_list_2025.xlsx", "Nivarque Price List 2025 (superseded on 1 October 2026)", [
        ["Nivarque Core", "Starter", "per user per month", 16, "12 months"],
        ["Nivarque Core", "Business", "per user per month", 30, "12 months"],
        ["Nivarque Engineering Vault", "Enterprise", "per user per month", 48, "24 months"],
        ["Records Retention Add-on", "Add-on", "per TB per month", 220, "12 months"],
    ], ["Effective from 1 October 2025 until 30 September 2026.", "Superseded by NVQ-PRC-2026-v1."])

    price_list("NVQ-PRC-2026-v1_price_list_2026.xlsx", "Nivarque Price List 2026 (approved, current)", [
        ["Nivarque Core", "Starter", "per user per month", 18, "12 months"],
        ["Nivarque Core", "Business", "per user per month", 34, "12 months"],
        ["Nivarque Engineering Vault", "Enterprise", "per user per month", 52, "24 months"],
        ["Records Retention Add-on", "Add-on", "per TB per month", 240, "12 months"],
    ], ["Effective from 1 October 2026 until replaced by a newer approved price list.",
        "List prices exclude VAT and are billed annually in advance."])

    header = ["Product", "Tier", "Quantity", "Unit", "Proposed price (USD)", "Valid until"]
    proposal("NVQ-PRP-001_shikun_binui_proposal.docx", "Proposal: Nivarque Engineering Vault for Shikun & Binui", [
        ("Scope", ["Nivarque proposes Engineering Vault for 400 users to manage the drawing register and transmittals "
                   "exchanged with contractors.",
                   "This proposal was sent on 12 October 2026. No decision has been recorded."]),
        ("Commercial terms", ["The proposed Engineering Vault price is 49 USD per user per month, a discount of about "
                              "5.8 percent from the 2026 list price, within account executive authority."]),
    ], header, [
        ["Nivarque Engineering Vault", "Enterprise", "400", "per user per month", "49", "31 December 2026"],
        ["Records Retention Add-on", "Add-on", "20", "per TB per month", "240", "31 December 2026"],
    ])

    proposal("NVQ-PRP-002_arup_proposal.docx", "Proposal: Nivarque Engineering Vault for Arup (negotiation)", [
        ("Scope", ["Nivarque proposes Engineering Vault for 1,200 users on a 36-month term, plus a fixed-fee "
                   "implementation package.",
                   "The deal is in negotiation; Arup will confirm the user count by 30 November 2026."]),
        ("Commercial terms", ["The negotiated Engineering Vault price is 46 USD per user per month, a discount of about "
                              "11.5 percent from the 2026 list price of 52, within account executive authority. "
                              "This negotiated price applies only to this proposal and does not change the list price."]),
    ], header, [
        ["Nivarque Engineering Vault", "Enterprise", "1200", "per user per month", "46", "15 December 2026"],
        ["Implementation Services", "Service", "1", "per project (fixed fee)", "85000", "15 December 2026"],
    ])

    policy_pdf("NVQ-POL-001_commercial_policy.pdf", [
        [VENDOR_BANNER],
        ["Discount approval policy",
         "Account executives may approve discounts of up to 15 percent from the list price.",
         "Discounts above 15 percent require written approval from the regional sales director.",
         "Discounts above 25 percent require approval from the CFO."],
        ["Billing terms",
         "List prices exclude VAT. Per-user products are billed annually in advance in USD."],
        ["Proposal validity",
         "Proposals are valid for 60 days unless a different date is stated.",
         "Negotiated prices apply only to the customer and validity period of that proposal and never change the list price."],
    ])
    print(f"Generated 5 files in {OUT}")


if __name__ == "__main__":
    main()
