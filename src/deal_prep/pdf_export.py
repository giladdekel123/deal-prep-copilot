"""Briefing PDF in English or Hebrew (Prompt 05; spec FR-09, AT-06).

English uses the built-in Helvetica font. Hebrew uses a Unicode TrueType font (Arial on Windows by
default; override with DEAL_PREP_FONT_DIR) with right-to-left text shaping (uharfbuzz) and right
alignment. Section content, sources and other dynamic text are wrapped in Unicode first-strong
isolates, so English content keeps its own punctuation and references inside a Hebrew page, and
Hebrew content (when a model drafts in Hebrew) runs right-to-left automatically.

Pagination and type (presentation-only change, owner and ChatGPT review of the rendered PDF, 2026-11-20; the
historical specification is unchanged): the briefing flows over as many pages as it needs, at the largest body size
that fits in MAX_PAGES pages (10 pt, then 9.5, then 9). No text anywhere is smaller than MIN_FONT (9 pt). Every
page has a footer ("page n of N"). Two readable pages are preferred to one crowded page; nothing is shortened or
dropped, and an overflow beyond MAX_PAGES at MIN_FONT is reported (PdfOverflow). Section headings are larger, with
a rule under them, and are kept together with the first lines that follow; items are separated by a small gap.

Header: the title, one line with the purpose and creation time, the research/news labels, then the synthetic-records
notice (and the saved-demonstration notice) in a shaded box. Technical run metadata (the run ID and the generation
label that names the model) moves to a "Run details" block after the sources, in smaller grey type; it is not removed.

Reader-facing disclosures (reader_disclosures, shared with the on-screen briefing): a model note about an optional
eligibility check (topic_gap:eligibility:...) is hidden only when it is internal or redundant: no briefing item
mentions that capability, or every item that does already states its limit. A note about a capability an item
mentions without its limit is a material warning and is kept. Every other disclosure is shown verbatim.

Sources (Phase 4.5 I6): cited passages of the same document with the same provenance label share one numbered
line ("DOC#1, #3: label"), so a document cited through several passages is listed once. Every cited passage ID is
still listed. In English each source is a numbered entry with a hanging indent (the number stands apart, long
identifiers and URLs wrap inside the text column); source lines are not justified, so long URLs do not stretch the
line. An empty section keeps its heading and shows, in muted italic, the drafter's own reason when the briefing
carries one (section_notes), otherwise the standard statement that no supported content was available.

Layout (Phase 4.5 I6): items, notes, disclosures and sources are indented under their heading (on the right in
Hebrew). Only position, spacing and type change; the text is the same.
"""
import os
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SECTION_KEYS = ("company_overview", "recent_developments", "our_relationship", "opportunities",
                "competitive_positioning", "meeting_recommendations")
FONT_SIZES = (10.0, 9.5, 9.0)  # body size: the largest that fits MAX_PAGES pages
MIN_FONT = FONT_SIZES[-1]  # 9 pt: the floor for every piece of text on the page
MAX_PAGES = 4
MARGIN_X_MM = 18.0  # left and right margin
MARGIN_Y_MM = 16.0  # top margin and bottom margin above the footer
FOOTER_MM = 8.0  # space kept free at the bottom of every page for its footer
INDENT_MM = 4.0  # items under their heading
SOURCE_NUM_MM = 9.0  # English sources: width of the number column (hanging indent)
LEADING = 0.50  # line height in mm per point of font size (about 1.4 x the font size)
ITEM_GAP = 0.45  # gap after an item, as a fraction of the line height
HEADING_GAP_MM = 4.5  # space above a section heading
INK = (0, 0, 0)  # body text
HEAD_INK = (24, 38, 64)  # headings: dark navy
MUTED = (85, 85, 85)  # run metadata, empty-section lines, footer
RULE = (170, 170, 170)  # thin line under headings
BOX = (238, 241, 245)  # shaded notice box
FSI, LRI, PDI = "\u2068", "\u2066", "\u2069"  # first-strong / left-to-right isolates

TEXT = {
    "en": {
        "sections": {"company_overview": "1. Company overview", "recent_developments": "2. Recent developments",
                     "our_relationship": "3. Our relationship (synthetic demonstration records)",
                     "opportunities": "4. Potential opportunities",
                     "competitive_positioning": "5. Competitive positioning",
                     "meeting_recommendations": "6. Meeting recommendations"},
        "kind": {"fact": "FACT", "inference": "ANALYSIS", "recommendation": "RECOMMENDATION"},
        "origin": {"public_source": "public", "synthetic_record": "synthetic"},
        "purpose": {"general": "general", "introduction": "introduction", "product_demo": "product demo",
                    "negotiation": "negotiation", "follow_up": "follow up"},
        "title": "Meeting briefing: {name}",
        "meta": "Purpose: {purpose} | Created: {created}",
        "run_details": "Run details",
        "run": "Run ID: {run}",
        "labels": "Research: {completeness} | News: {news}",
        "notice": "Contains SYNTHETIC demonstration records about the fictional vendor Nivarque Document Systems; "
                  "they are not real business facts. Public facts cite their sources below.",
        "saved": "SIMULATED SAVED DEMONSTRATION: created {created}; not newly researched.",
        "empty": "No supported content (see gaps below).",
        "empty_note": "No supported content: {note}",
        "gaps": "Gaps, conflicts and limitations",
        "sources": "Sources",
        "footer": "Meeting briefing: {name} - page {page} of {total}",
        "content_note": "",
    },
    "he": {
        "sections": {"company_overview": "1. סקירת החברה", "recent_developments": "2. התפתחויות אחרונות",
                     "our_relationship": "3. הקשר שלנו (רשומות הדגמה סינתטיות)",
                     "opportunities": "4. הזדמנויות אפשריות", "competitive_positioning": "5. מיצוב תחרותי",
                     "meeting_recommendations": "6. המלצות לפגישה"},
        "kind": {"fact": "עובדה", "inference": "ניתוח", "recommendation": "המלצה"},
        "origin": {"public_source": "ציבורי", "synthetic_record": "סינתטי"},
        "purpose": {"general": "כללית", "introduction": "היכרות", "product_demo": "הדגמת מוצר",
                    "negotiation": "משא ומתן", "follow_up": "מעקב"},
        "title": "תדריך פגישה: {name}",
        "meta": "מטרה: {purpose} | נוצר: {created}",
        "run_details": "פרטי הרצה",
        "run": "מזהה הרצה: {run}",
        "labels": "מחקר: {completeness} | חדשות: {news}",
        "notice": "מכיל רשומות הדגמה סינתטיות על הספק הבדיוני Nivarque Document Systems; אין הן עובדות "
                  "עסקיות אמיתיות. עובדות ציבוריות מצוטטות עם מקורותיהן להלן.",
        "saved": "הדגמה שמורה מדומה (SIMULATED): נוצרה ב-{created}; לא נחקרה מחדש.",
        "empty": "אין תוכן נתמך (ראו פערים להלן).",
        "empty_note": "אין תוכן נתמך: {note}",
        "gaps": "פערים, סתירות ומגבלות",
        "sources": "מקורות",
        "footer": "תדריך פגישה: {name} - עמוד {page} מתוך {total}",
        "content_note": "תוכן הסעיפים מוצג בשפת המקור (אנגלית); ניסוח התוכן בעברית טרם הופעל.",
    },
}
# Back-compatible English names used by the Streamlit page.
SECTION_TITLES = TEXT["en"]["sections"]
KIND_TAG = TEXT["en"]["kind"]
ORIGIN_TAG = TEXT["en"]["origin"]
NOTICE = TEXT["en"]["notice"]
_ASCII = {"\u2014": "-", "\u2013": "-", "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
          "\u2026": "...", "\u00b7": "|", "\u2192": "->", "\u00a0": " "}


class PdfOverflow(RuntimeError):
    pass


class HebrewFontMissing(RuntimeError):
    pass


def _font_files() -> dict[str, Path]:
    base = Path(os.environ.get("DEAL_PREP_FONT_DIR", "C:/Windows/Fonts"))
    files = {"": base / "arial.ttf", "B": base / "arialbd.ttf", "I": base / "ariali.ttf"}
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise HebrewFontMissing(f"Hebrew PDF needs a Unicode font with Hebrew glyphs; not found: {missing}. "
                                "Set DEAL_PREP_FONT_DIR to a folder containing arial.ttf, arialbd.ttf and ariali.ttf.")
    return files


def _latin(text: str) -> str:
    for k, v in _ASCII.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


_ELIGIBILITY_NOTE = "topic_gap:eligibility:"


def reader_disclosures(result: dict) -> list[dict]:
    """The disclosures a reader sees (PDF and on-screen). A model note about an optional eligibility check
    (topic_gap:eligibility:<id>) is hidden only when it is internal or redundant, judged against the analysis entry it
    refers to: no briefing item mentions that capability (it explains something not proposed), or every item that does
    already states the limit. If any item mentions the capability without its limit, the note is a material warning
    and is kept; it is also kept when the analysis entry is not available. Every other disclosure is unchanged."""
    entries = {e["id"]: e for e in ((result.get("business_analysis") or {}).get("eligibility") or [])}
    items = [i for its in (result.get("briefing") or {}).values() for i in its]
    shown = []
    for d in result.get("disclosures") or []:
        did = str(d.get("id", ""))
        e = entries.get(did[len("topic_gap:"):]) if did.startswith(_ELIGIBILITY_NOTE) else None
        if e is None:
            shown.append(d)
            continue
        triggers = [rf"\b{re.escape(w)}" for w in e.get("triggers") or []]
        using = [i for i in items if e["evidence_id"] in i.get("evidence_ids", [])
                 and (not triggers or any(re.search(t, i["text"], re.I) for t in triggers))]
        limited = all(re.search(rf"\b{re.escape(e['marker'])}\b", i["text"], re.I) for i in using)
        if using and not limited:  # a capability mentioned without its limit: the note is a material warning
            shown.append(d)
    return shown


def _chunk_no(eid: str) -> int:
    tail = eid.rsplit("#", 1)[-1]
    return int(tail) if "#" in eid and tail.isdigit() else -1


def source_groups(result: dict) -> list[dict]:
    """Cited passages grouped by document, in order of first citation (items, then disclosures such as both sides
    of an unresolved conflict). Passages of one document with different provenance labels stay separate, so no
    label is ever lost. Returns [{"document", "label", "evidence_ids"}], passages in document order."""
    evidence = result.get("evidence", {})
    cited = [eid for items in (result.get("briefing") or {}).values() for item in items for eid in item["evidence_ids"]]
    cited += [eid for d in result.get("disclosures", []) for eid in d.get("evidence_ids", [])]
    groups: dict[tuple, list[str]] = {}
    for eid in dict.fromkeys(cited):
        key = (eid.split("#")[0], evidence.get(eid, {}).get("provenance_label", eid))
        groups.setdefault(key, []).append(eid)
    return [{"document": doc, "label": label, "evidence_ids": sorted(ids, key=_chunk_no)}
            for (doc, label), ids in groups.items()]


def _source_numbers(result: dict) -> dict[str, int]:
    """Passage ID -> its source line number (passages of one document share a number)."""
    return {eid: n for n, g in enumerate(source_groups(result), 1) for eid in g["evidence_ids"]}


def _refs(ids: list[str], numbers: dict[str, int]) -> str:
    return "".join(f"[{n}]" for n in dict.fromkeys(numbers[e] for e in ids if e in numbers))


def _source_ids(group: dict) -> str:
    """'DOC#1' for one passage; 'DOC#1, #3' for several (every passage ID stays visible)."""
    first, *rest = group["evidence_ids"]
    return ", ".join([first] + [e[len(group["document"]):] if e.startswith(group["document"] + "#") else e
                                for e in rest])


class _Page(FPDF):
    """A4 page; every page carries a footer (company and page n of N) at MIN_FONT, in muted italic."""
    footer_text = None  # callable(page) -> str
    footer_family = "Helvetica"
    footer_rtl = False

    def footer(self):
        if not self.footer_text:
            return
        self.set_y(-(FOOTER_MM + 6))
        self.set_font(self.footer_family, "I", MIN_FONT)
        self.set_text_color(*MUTED)
        s = self.footer_text(self.page_no())
        self.cell(0, MIN_FONT * 0.47, s if self.footer_rtl else _latin(s), align="R" if self.footer_rtl else "C")
        self.set_text_color(*INK)


def _render(result: dict, size: float, generation_label: str, lang: str, total_pages: int = 1) -> FPDF:
    """One render at body size 'size'. The footer says 'page n of total_pages'; its space is kept free on every
    page, so the page breaks do not depend on the number printed."""
    t = TEXT[lang]
    rtl = lang == "he"
    pdf = _Page(format="A4")
    pdf.set_margins(MARGIN_X_MM, MARGIN_Y_MM, MARGIN_X_MM)
    pdf.set_auto_page_break(True, margin=MARGIN_Y_MM + FOOTER_MM)
    family = "Helvetica"
    if rtl:
        for style, path in _font_files().items():
            pdf.add_font("BriefingUnicode", style, str(path))
        family = "BriefingUnicode"
        pdf.set_text_shaping(use_shaping_engine=True, direction="rtl")
    floor = MIN_FONT  # no text below 9 pt
    name = (result.get("identity") or {}).get("name") or result["company_input"]
    pdf.footer_family, pdf.footer_rtl = family, rtl
    pdf.footer_text = lambda page: t["footer"].format(
        name=f"{FSI}{name}{PDI}" if rtl else name,
        page=f"{LRI}{page}{PDI}" if rtl else page, total=f"{LRI}{total_pages}{PDI}" if rtl else total_pages)
    pdf.add_page()
    w = pdf.epw
    small = max(size - 1.0, floor)  # metadata, notices, sources

    def iso(s: str) -> str:  # dynamic content keeps its own direction inside the page
        return f"{FSI}{s}{PDI}" if rtl else s

    def ltr(s: str) -> str:  # identifiers and dates are always left-to-right (e.g. a run ID starting with digits)
        return f"{LRI}{s}{PDI}" if rtl else s

    def text(s, style="", sz=None, gap=0.0, indent=0.0, align="L", ink=INK, fill=False):
        sz = max(sz or size, floor)  # every line, including metadata, notices and sources, is at least MIN_FONT
        pdf.set_font(family, style, sz)
        pdf.set_text_color(*ink)
        pdf.set_x(pdf.l_margin + (0.0 if rtl else indent))  # Hebrew: the indent is on the right
        pdf.multi_cell(w - indent, sz * LEADING, s if rtl else _latin(s), align="R" if rtl else align,
                       new_x="LMARGIN", new_y="NEXT", fill=fill)
        pdf.set_text_color(*INK)
        if gap:
            pdf.ln(gap)

    def entry(s, style="", sz=None, ink=INK):  # an indented item, note or disclosure, with a gap after it
        text(s, style, sz, gap=(sz or size) * LEADING * ITEM_GAP, indent=INDENT_MM, ink=ink)

    def heading(s):  # larger bold heading with a rule, kept together with the lines that follow it
        sz = size + 2.0
        need = HEADING_GAP_MM + sz * LEADING + 2 + 2 * size * LEADING
        if pdf.get_y() + need > pdf.page_break_trigger:
            pdf.add_page()
        elif pdf.get_y() > pdf.t_margin + 1:
            pdf.ln(HEADING_GAP_MM)
        text(s, "B", sz, ink=HEAD_INK)
        y = pdf.get_y() + 0.6
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, y, pdf.l_margin + w, y)
        pdf.ln(1.8)

    created_dt = datetime.fromisoformat(result["created_at"])
    created = created_dt.strftime("%Y-%m-%d %H:%M UTC") if rtl else created_dt.strftime("%d %b %Y %H:%M UTC")
    labels = result.get("labels", {})
    purpose = t["purpose"].get(result["purpose"], result["purpose"])
    text(t["title"].format(name=iso(name)), "B", size + 6, gap=1.2, ink=HEAD_INK)
    text(t["meta"].format(purpose=purpose, created=ltr(created)), sz=small, ink=MUTED)
    text(t["labels"].format(completeness=iso(labels.get("completeness", "-")),
                            news=iso(labels.get("market_intelligence", "-"))), sz=small, ink=MUTED, gap=2.0)
    pdf.set_fill_color(*BOX)
    if result.get("saved_demo"):
        text(t["saved"].format(created=ltr(created)), "B", small, ink=HEAD_INK, fill=True, gap=1.0)
    text(t["notice"], "B", small, ink=HEAD_INK, fill=True)
    if t["content_note"]:
        text(t["content_note"], "I", small, ink=MUTED)

    numbers, evidence = _source_numbers(result), result.get("evidence", {})
    notes = result.get("section_notes") or {}
    for key in SECTION_KEYS:
        items = (result.get("briefing") or {}).get(key, [])
        heading(t["sections"][key])
        if not items:  # the heading stays; the line below says plainly that nothing supported was available
            entry(t["empty_note"].format(note=iso(notes[key])) if notes.get(key) else t["empty"], "I", ink=MUTED)
        for item in items:  # nothing is shortened or dropped (owner-approved change to FR-09/AT-06)
            body = item["text"]
            origins = sorted({t["origin"][evidence[e]["info_origin"]] for e in item["evidence_ids"] if e in evidence})
            tag = t["kind"][item["kind"]] + (f", {'/'.join(origins)}" if item["kind"] == "fact" and origins else "")
            refs = _refs(item["evidence_ids"], numbers)
            entry(f"[{tag}] " + iso(f"{body} {refs}".rstrip()))

    disclosures = result.get("disclosures", [])  # build_pdf passes the reader-facing disclosures
    if disclosures:
        heading(t["gaps"])
        for d in disclosures:
            refs = _refs(d.get("evidence_ids", []), numbers)
            entry("- " + iso(f"{d['text']} {refs}".rstrip()))
    if numbers:
        heading(t["sources"])
        lh = small * LEADING
        for n, group in enumerate(source_groups(result), 1):
            line = iso(f"{_source_ids(group)}: {group['label']}")
            if rtl:  # right-to-left: the number stays in the text line
                text(f"[{n}] " + line, sz=small, gap=lh * 0.35, indent=INDENT_MM)
                continue
            if pdf.get_y() + 2 * lh > pdf.page_break_trigger:  # the number never stands alone at a page bottom
                pdf.add_page()
            pdf.set_font(family, "", small)
            pdf.set_x(pdf.l_margin + INDENT_MM)
            pdf.cell(SOURCE_NUM_MM, lh, f"[{n}]", new_x="RIGHT", new_y="TOP")
            pdf.multi_cell(w - INDENT_MM - SOURCE_NUM_MM, lh, _latin(line), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(lh * 0.35)
    # Technical run metadata: after the sources, smaller and muted; nothing is removed.
    heading(t["run_details"])
    text(t["run"].format(run=ltr(result["run_id"])), sz=small, ink=MUTED, indent=INDENT_MM)
    if generation_label:
        text(iso(generation_label), "I", small, ink=MUTED, indent=INDENT_MM)
    return pdf


def build_pdf(result: dict, generation_label: str = "", language: str = "en") -> tuple[bytes, dict]:
    """Return (pdf_bytes, info). info: language, font_size, pages, item_spacing (always True: the gap between items
    is no longer traded for font size), hidden_notes, and shortened (always False: content is never shortened; kept for
    callers that read it)."""
    if language not in TEXT:
        raise ValueError(f"language must be one of {sorted(TEXT)}")
    if not result.get("briefing"):
        raise ValueError("no briefing to export")
    shown = reader_disclosures(result)
    view = {**result, "disclosures": shown}  # sources are numbered from what the reader sees
    hidden = len(result.get("disclosures") or []) - len(shown)
    for size in FONT_SIZES:  # the largest body size whose briefing fits MAX_PAGES readable pages; never smaller than 9 pt
        first = _render(view, size, generation_label, language, MAX_PAGES)
        if first.page_no() <= MAX_PAGES:
            final = _render(view, size, generation_label, language, first.page_no())
            return bytes(final.output()), {"language": language, "font_size": size, "shortened": False,
                                           "pages": final.page_no(), "item_spacing": True, "hidden_notes": hidden}
    raise PdfOverflow(f"briefing does not fit on {MAX_PAGES} readable pages")
