"""Phase 4.5 I6: briefing-shape measurements on saved DEVELOPMENT run records (no rerun, no API call).
FICTIONAL TEST DATA: every benchmark company, source and record is fictional.

Usage: python scripts/briefing_shape.py <records.json> [<records.json> ...] [--json out.json]

Reads benchmark run records ({"records": [...]}, live or offline) and reports deterministic measures of how each
briefing is organised and how long it is. They describe SHAPE, not quality: a shorter briefing is not better by
itself, and relevance and reasoning are judged only by the manual audit. The scorer is not changed or replaced.
Held-out records are refused.

Measures (rule coverage):
- words and items per section, longest item (full);
- empty sections, and how many carry the drafter's reason (`section_notes`, I6; "n/a" for earlier records) (full);
- empty Opportunities in a scenario whose drafting input holds this customer's relationship records (full);
- Competitive-positioning items citing no competitor evidence (`internal:competition`) (full);
- figures and dates stated in more than one section (approximation: the same token, not necessarily the same fact;
  years, document IDs and digits inside dates are not counted as figures);
- one-page PDF with the current pdf_export: font size, shortened or not, whether the gap between items was kept
  (I6 Phase 2), and source lines per cited passage versus grouped by document (full, for this renderer).
"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from deal_prep.contract import figures  # noqa: E402
from deal_prep.pdf_export import MIN_FONT, SECTION_KEYS, PdfOverflow, build_pdf, source_groups  # noqa: E402

LABEL = "FICTIONAL TEST DATA - fictional benchmark companies, sources and records (development split only)."
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_M = "|".join(_MONTHS)
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})\s+({_M})\b|\b({_M})\s+(\d{{1,2}})\b", re.I)
_ISO = re.compile(r"\b(?:19|20)\d{2}-(\d{2})-(\d{2})\b")
SHORT = {"company_overview": "overview", "recent_developments": "recent", "our_relationship": "relationship",
         "opportunities": "opportunities", "competitive_positioning": "competitive",
         "meeting_recommendations": "recommendations"}


def load_dev_records(path: Path) -> list[dict]:
    """Development records only: a held-out path or any non-DEV scenario is refused (nothing is read further)."""
    p = Path(path).resolve()
    if "heldout" in p.as_posix().casefold():
        raise PermissionError("held-out records are never read by development tools")
    records = json.loads(p.read_text(encoding="utf-8"))["records"]
    if not all(str(r.get("scenario", "")).startswith("DEV-") for r in records):
        raise PermissionError("only development scenarios (DEV-*) are measured by development tools")
    return records


def dates(text: str) -> set[str]:
    """Day-and-month dates as "<day> <month>" (year ignored, so "16 November" and "16 November 2026" match)."""
    out = set()
    for m in _DAY_MONTH.finditer(text):
        day, month = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        out.add(f"{int(day)} {month.casefold()}")
    for m in _ISO.finditer(text):
        out.add(f"{int(m.group(2))} {_MONTHS[int(m.group(1)) - 1]}")
    return out


def tokens(text: str) -> set[str]:
    """Figures and dates an item states (see the module docstring for what is excluded)."""
    without_dates = _ISO.sub(" ", _DAY_MONTH.sub(" ", text))
    return {f"date:{d}" for d in dates(text)} | {f"figure:{n.replace(',', '')}" for n in figures(without_dates)}


def repeated_across_sections(briefing: dict) -> dict[str, list[str]]:
    """token -> the sections stating it, for tokens stated in two or more sections."""
    seen: dict[str, set[str]] = {}
    for section, items in briefing.items():
        for item in items:
            for tok in tokens(item["text"]):
                seen.setdefault(tok, set()).add(section)
    return {tok: sorted(s, key=SECTION_KEYS.index) for tok, s in sorted(seen.items()) if len(s) > 1}


def pdf_shape(record: dict) -> dict:
    briefing = record.get("briefing") or {}
    result = {"created_at": record.get("clock") or "2026-11-09T09:00:00+00:00",
              "identity": {"name": record.get("company", "")}, "company_input": record.get("company", ""),
              "labels": record.get("labels") or {}, "purpose": record.get("purpose", "general"),
              "run_id": "shape-check", "briefing": briefing, "disclosures": record.get("disclosures") or [],
              "evidence": record.get("drafting_input") or {}, "section_notes": record.get("section_notes") or {}}
    passages = {e for items in briefing.values() for i in items for e in i["evidence_ids"]}
    passages |= {e for d in result["disclosures"] for e in d.get("evidence_ids", [])}
    try:
        _, info = build_pdf(result)
        fit = {"font_size": info["font_size"], "shortened": info["shortened"], "overflow": False,
               "item_spacing": info.get("item_spacing")}
    except PdfOverflow:  # reported, never hidden; any other error is a defect and propagates
        fit = {"font_size": None, "shortened": None, "overflow": True, "item_spacing": None}
    return {**fit, "source_lines_per_passage": len(passages), "source_lines_grouped": len(source_groups(result))}


def measure(record: dict) -> dict:
    briefing = record.get("briefing") or {}
    di = record.get("drafting_input") or {}
    words = {s: sum(len(i["text"].split()) for i in briefing.get(s, [])) for s in SECTION_KEYS}
    empty = [s for s in SECTION_KEYS if not briefing.get(s)]
    notes = record.get("section_notes")
    customer = any(e.get("source") == "internal:relationship_history" for e in di.values())
    off_label = [i["text"][:80] for i in briefing.get("competitive_positioning", [])
                 if not any((di.get(e) or {}).get("source") == "internal:competition" for e in i["evidence_ids"])]
    repeated = repeated_across_sections(briefing)
    lengths = [len(i["text"].split()) for items in briefing.values() for i in items]
    return {"scenario": record["scenario"], "purpose": record.get("purpose"), "news_mode": record.get("news_mode"),
            "status": record.get("status"), "customer": customer,
            "words": sum(words.values()), "words_per_section": words,
            "items_per_section": {s: len(briefing.get(s, [])) for s in SECTION_KEYS},
            "longest_item_words": max(lengths, default=0),
            "empty_sections": empty,
            "empty_with_reason": (None if notes is None else sum(1 for s in empty if notes.get(s))),
            "empty_opportunities_customer": customer and "opportunities" in empty,
            "competitive_items_without_competitor_evidence": off_label,
            "repeated_tokens": repeated, "pdf": pdf_shape(record) if briefing else None}


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["pdf"]]
    fonts = [r["pdf"]["font_size"] for r in ok if r["pdf"]["font_size"] is not None]
    return {"briefings": len(rows), "with_briefing": len(ok),
            "median_words": statistics.median([r["words"] for r in ok]) if ok else None,
            "max_words": max((r["words"] for r in ok), default=None),
            "empty_opportunities_customer": f"{sum(r['empty_opportunities_customer'] for r in ok)} / "
                                            f"{sum(r['customer'] for r in ok)}",
            "competitive_items_without_competitor_evidence": sum(
                len(r["competitive_items_without_competitor_evidence"]) for r in ok),
            "repeated_tokens": sum(len(r["repeated_tokens"]) for r in ok),
            "pdf_min_font": min(fonts, default=None),
            "pdf_at_minimum_font": sum(1 for f in fonts if f == MIN_FONT),
            "pdf_shortened": sum(1 for r in ok if r["pdf"]["shortened"]),
            "pdf_overflow": sum(1 for r in ok if r["pdf"]["overflow"]),
            "pdf_item_spacing": sum(1 for r in ok if r["pdf"].get("item_spacing")),
            "source_lines_per_passage": sum(r["pdf"]["source_lines_per_passage"] for r in ok),
            "source_lines_grouped": sum(r["pdf"]["source_lines_grouped"] for r in ok)}


def report(path: Path) -> dict:
    rows = [measure(r) for r in load_dev_records(path) if not r.get("error")]
    return {"label": LABEL, "source": Path(path).as_posix(), "rows": rows, "summary": summarize(rows)}


def markdown(rep: dict) -> str:
    out = [f"### {rep['source']}", "", LABEL, "",
           "| Scenario | Purpose | News | Words | Empty sections | Comp. items w/o competitor | Repeated tokens "
           "| PDF font | Shortened | Source lines (passage -> grouped) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["rows"]:
        p = r["pdf"] or {}
        empty = ", ".join(SHORT[s] for s in r["empty_sections"]) or "-"
        out.append(f"| {r['scenario']} | {r['purpose']} | {r['news_mode'] or '-'} | {r['words']} | {empty} | "
                   f"{len(r['competitive_items_without_competitor_evidence'])} | {len(r['repeated_tokens'])} | "
                   f"{p.get('font_size')} | {p.get('shortened')} | "
                   f"{p.get('source_lines_per_passage')} -> {p.get('source_lines_grouped')} |")
    s = rep["summary"]
    out += ["", "Summary: " + "; ".join(f"{k} {v}" for k, v in s.items()), ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("records", nargs="+", type=Path)
    ap.add_argument("--json", type=Path, help="also write the full measurements as JSON")
    args = ap.parse_args(argv)
    reports = [report(p) for p in args.records]
    print("\n".join(markdown(r) for r in reports))
    if args.json:
        args.json.write_text(json.dumps(reports, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
