"""PDF readability (owner-approved 2026-11-15, revised 2026-11-20; a change to FR-09/AT-06, the historical
specification is unchanged): body type about 10 pt and no text below 9 pt anywhere (metadata, notices, sources, footer,
Hebrew), natural pagination with a footer on every page instead of squeezing onto one page, nothing shortened or
dropped, run metadata kept but moved after the sources, and internal/redundant eligibility notes hidden from readers
(PDF and screen) while material eligibility warnings and every other disclosure stay verbatim."""
import io
import json
from pathlib import Path

import pytest
from fpdf import FPDF
from pypdf import PdfReader

from deal_prep import pdf_export
from deal_prep.pdf_export import MAX_PAGES, MIN_FONT, build_pdf, reader_disclosures

ROOT = Path(__file__).resolve().parents[1]
EV = {"PUB#1": {"provenance_label": "PUBLIC SOURCE | Example Org | https://example.org/about | published 2026-01-01",
                "info_origin": "public_source"},
      "PRD#4": {"provenance_label": "SYNTHETIC - not a real business fact | vendor product overview",
                "info_origin": "synthetic_record"},
      "PRD#0": {"provenance_label": "SYNTHETIC - not a real business fact | vendor product overview",
                "info_origin": "synthetic_record"}}
ELIG = [{"id": "eligibility:PRD#4:1", "evidence_id": "PRD#4", "marker": "Engineering Vault",
         "triggers": ["private-cloud", "single-tenant"], "limit": "the source says it is for Engineering Vault customers"},
        {"id": "eligibility:PRD#0:2", "evidence_id": "PRD#0", "marker": "Business", "triggers": ["workflows"],
         "limit": "the source says the Business tier adds it"}]


def item(kind, text, ids):
    return {"kind": kind, "text": text, "evidence_ids": ids, "claim_type": "real_world_fact" if kind == "fact" else None}


def result(recs=(), disclosures=(), n_extra=0, eligibility=ELIG):
    briefing = {k: [] for k in pdf_export.SECTION_KEYS}
    briefing["company_overview"] = [item("fact", "Example Org operated 4 sites at the end of 2025.", ["PUB#1"])]
    briefing["meeting_recommendations"] = [item("recommendation", t, ids) for t, ids in recs]
    briefing["meeting_recommendations"] += [
        item("recommendation", f"Extra action {i}: confirm the scope and owner of this follow-up step. " * 4, ["PUB#1"])
        for i in range(n_extra)]
    return {"created_at": "2026-11-09T09:00:00+00:00", "identity": {"name": "Example Org"}, "company_input": "Example Org",
            "labels": {"completeness": "complete", "market_intelligence": "current"}, "purpose": "product_demo",
            "run_id": "test-run", "briefing": briefing, "disclosures": list(disclosures), "evidence": EV,
            "section_notes": {}, "business_analysis": {"eligibility": eligibility}}


NOTE_EV = {"id": "topic_gap:eligibility:PRD#4:1", "kind": "topic_gap",
           "text": "The evidence does not establish an Engineering Vault fit, so private cloud is not proposed."}
NOTE_WF = {"id": "topic_gap:eligibility:PRD#0:2", "kind": "topic_gap",
           "text": "Approval-workflow eligibility is addressed in the demonstration plan."}
CONFLICT = {"id": "conflict:derived:figures:1", "kind": "unresolved_conflict", "evidence_ids": ["PUB#1"],
            "text": "Unresolved conflict: two sources give different figures; neither is treated as established."}
TOPIC_GAP = {"id": "topic_gap:price_position:PRP#2", "kind": "topic_gap",
             "text": "The price position cannot be calculated: the list price is missing."}


# --- reader-facing disclosures ---------------------------------------------------------------------------------

def test_a_note_about_a_capability_no_item_mentions_is_hidden():
    r = result([("Show version control and search.", ["PRD#0"])], [NOTE_EV, CONFLICT, TOPIC_GAP])
    assert reader_disclosures(r) == [CONFLICT, TOPIC_GAP]


def test_a_note_is_hidden_when_every_item_mentioning_the_capability_states_its_limit():
    r = result([("Show configurable approval workflows on the Business tier.", ["PRD#0"])], [NOTE_WF])
    assert reader_disclosures(r) == []


def test_a_material_warning_is_kept_when_an_item_mentions_the_capability_without_its_limit():
    r = result([("Offer a single-tenant private-cloud deployment for data residency.", ["PRD#4"])], [NOTE_EV])
    assert reader_disclosures(r) == [NOTE_EV]
    r = result([("Show configurable approval workflows to the team.", ["PRD#0"])], [NOTE_WF])
    assert reader_disclosures(r) == [NOTE_WF]


def test_notes_are_kept_when_the_analysis_entry_is_not_available():
    r = result([], [NOTE_EV], eligibility=[])
    assert reader_disclosures(r) == [NOTE_EV]
    r.pop("business_analysis")
    assert reader_disclosures(r) == [NOTE_EV]


def test_the_on_screen_briefing_uses_the_same_reader_disclosures():
    app = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "shown = reader_disclosures(result)" in app and "for d in shown:" in app


def test_hidden_notes_are_not_printed_and_other_disclosures_are_printed_verbatim():
    r = result([("Show version control and search.", ["PRD#0"])], [NOTE_EV, CONFLICT, TOPIC_GAP])
    data, info = build_pdf(r)
    flat = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages).split())
    assert info["hidden_notes"] == 1 and "Engineering Vault fit" not in flat
    assert CONFLICT["text"] in flat and TOPIC_GAP["text"] in flat


# --- 9 pt minimum, pages, footer ---------------------------------------------------------------------------------

class Sizes:
    def __init__(self, monkeypatch):
        self.seen, original = [], FPDF.set_font

        def spy(pdf, family=None, style="", size=0):
            self.seen.append(size)
            return original(pdf, family, style, size)
        monkeypatch.setattr(FPDF, "set_font", spy)


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("extra", [0, 12, 40])
def test_no_text_below_9_pt_on_one_or_more_pages(monkeypatch, language, extra):
    r = result([("Show version control and search.", ["PRD#0"])], [CONFLICT], n_extra=extra)
    sizes = Sizes(monkeypatch)
    data, info = build_pdf(r, language=language)
    pdf = PdfReader(io.BytesIO(data))
    assert min(sizes.seen) >= MIN_FONT == 9.0 and info["font_size"] >= MIN_FONT
    assert len(pdf.pages) == info["pages"] <= MAX_PAGES and not info["shortened"]
    flat = " ".join(" ".join(p.extract_text() for p in pdf.pages).split())
    for i in range(extra):  # nothing dropped
        assert f"Extra action {i}:" in flat, i


def test_a_short_briefing_is_set_at_ten_points_and_every_page_has_a_footer():
    data, info = build_pdf(result([("Show version control and search.", ["PRD#0"])], [CONFLICT]))
    text = " ".join(PdfReader(io.BytesIO(data)).pages[0].extract_text().split())
    assert info["pages"] == 1 and info["font_size"] == 10.0 and "page 1 of 1" in text


def test_a_longer_briefing_continues_at_a_larger_font_with_a_footer_on_every_page():
    data, info = build_pdf(result([("Show version control and search.", ["PRD#0"])], [CONFLICT], n_extra=40))
    pages = PdfReader(io.BytesIO(data)).pages
    assert info["pages"] == len(pages) >= 2 and info["font_size"] >= MIN_FONT  # readability over a single page
    for n, page in enumerate(pages, 1):
        assert f"Meeting briefing: Example Org - page {n} of {len(pages)}" in " ".join(page.extract_text().split())


def test_source_references_stay_correct_when_a_note_is_hidden():
    note = {**NOTE_EV, "evidence_ids": ["PRD#4"]}  # a hidden note's citation must not leave an orphan source
    r = result([("Show version control and search.", ["PRD#0"])], [note, CONFLICT])
    data, _ = build_pdf(r)
    flat = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages).split())
    assert "PRD#4" not in flat and "[1] PUB#1" in flat and "[2] PRD#0" in flat


@pytest.mark.parametrize("language", ["en", "he"])
def test_the_saved_demonstration_prints_on_readable_pages(language):
    saved = json.loads((ROOT / "data" / "demo" / "saved_briefing_shikun_binui.json").read_text(encoding="utf-8"))
    data, info = build_pdf(saved, saved.get("generation_label", ""), language)  # read only
    assert info["pages"] == len(PdfReader(io.BytesIO(data)).pages) <= 2 and info["font_size"] >= MIN_FONT


# --- layout (2026-11-20): run metadata, empty sections, sources ----------------------------------------------------

def _flat(data):
    return " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages).split())


def test_run_metadata_moves_after_the_sources_and_is_kept():
    r = result([("Show version control and search.", ["PRD#0"])], [CONFLICT])
    r["run_id"] = "run-abc-123"
    flat = _flat(build_pdf(r, "Drafted by a model from the cited evidence.")[0])
    assert "Run ID: run-abc-123" in flat and "Drafted by a model from the cited evidence." in flat
    assert flat.index("Sources") < flat.index("Run details") < flat.index("Run ID: run-abc-123") < flat.index("Drafted by a model")
    head = flat[:flat.index("1. Company overview")]
    assert "run-abc-123" not in head and "Drafted by" not in head
    assert "Purpose: product demo" in head and "Research: complete" in head and "SYNTHETIC demonstration records" in head


def test_an_empty_section_keeps_its_heading_and_states_that_nothing_was_supported():
    r = result([("Show version control and search.", ["PRD#0"])], [CONFLICT])
    flat = _flat(build_pdf(r)[0])
    for heading in ("2. Recent developments", "3. Our relationship (synthetic demonstration records)", "4. Potential opportunities"):
        i = flat.index(heading)
        assert flat[i + len(heading):].lstrip().startswith("No supported content (see gaps below).")


def test_sources_are_numbered_and_keep_their_full_identifiers_and_urls():
    r = result([("Show version control and search.", ["PRD#0"])], [CONFLICT])
    r["evidence"]["PUB#1"]["provenance_label"] = ("PUBLIC SOURCE | Example Org | https://example.org/" + "very-long-path-segment/" * 6
                                                  + "report.pdf | published 2026-01-01")
    flat = _flat(build_pdf(r)[0])
    assert "[1] PUB#1: PUBLIC SOURCE | Example Org | https://example.org/" in flat
    squashed = flat.replace(" ", "")
    assert ("very-long-path-segment/" * 6 + "report.pdf|published2026-01-01").replace(" ", "") in squashed
