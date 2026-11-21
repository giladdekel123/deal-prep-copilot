"""Prompt 05 (first slice): offline demo service, one-page English PDF, Streamlit page behaviour.

No paid calls and no credentials: live news is disabled and drafting uses the labelled template.
"""
import copy
import io
import re
from datetime import datetime
from pathlib import Path

import pytest
from pypdf import PdfReader

from deal_prep.app_service import BriefingService, load_saved_demo, request_key, save_demo
from deal_prep.demo import GENERATION_LABEL
from deal_prep.kb_index import build_kb_index
from deal_prep.pdf_export import MAX_PAGES, MIN_FONT, NOTICE, SECTION_TITLES, HebrewFontMissing, PdfOverflow, build_pdf

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("app_kb")
    build_kb_index(chroma_dir=d)
    return d


@pytest.fixture()
def service(kb):
    return BriefingService(chroma_dir=kb)


def pdf_text(data: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(data))
    return len(reader.pages), " ".join(p.extract_text() for p in reader.pages)


# --- offline demo service ---------------------------------------------------------------

def test_offline_demo_is_honestly_partial_and_spends_nothing(service):
    r, ran = service.get("Shikun & Binui", "", "general")
    assert ran and r["status"] == "partial_briefing"
    assert r["labels"]["market_intelligence"].startswith("not included")
    assert r["usage"]["tavily_credits"] == 0 and r["generation_label"] == GENERATION_LABEL
    assert any("does not include current market intelligence" in d["text"] for d in r["disclosures"])
    rel = r["briefing"]["our_relationship"]
    assert rel and all(item["text"].startswith("Synthetic demonstration record") for item in rel)
    assert all(r["evidence"][e]["info_origin"] == "synthetic_record" for item in rel for e in item["evidence_ids"])
    news = [t for t in r["trace"] if t["stage"] == "external_news"]
    assert news and all(t["outcome"].startswith("skipped") and t["credits"] == 0 for t in news)


def test_template_items_read_as_sentences_and_cite_the_right_material(service):
    # Found by visual PDF inspection: items began with section headings, and the competition
    # recommendation cited a price-list row while calling it a battlecard.
    from deal_prep.demo import _HEADINGS
    r, _ = service.get("Arup", "arup.com", "negotiation")
    for items in r["briefing"].values():
        for item in items:
            assert not any(item["text"].startswith(h + " ") for h in _HEADINGS), item["text"]
            assert not item["text"].startswith("Synthetic demonstration record: " + "Proposed pricing")
    comp = r["briefing"]["competitive_positioning"]
    # I3 (owner decision): Arup's evidence names no competitor, so no battlecard advice; when present it cites one.
    assert all(e.startswith("NVQ-CMP") for item in comp for e in item["evidence_ids"])
    assert not any("solquend" in item["text"].casefold() for items in r["briefing"].values() for item in items)
    s, _ = service.get("Shikun & Binui", "", "follow_up")
    assert all(not item["text"].startswith("PUBLIC SOURCE") for item in s["briefing"]["company_overview"])


def test_repeated_requests_reuse_the_cached_result(service):
    first, ran1 = service.get("Shikun & Binui", "", "general")
    again, ran2 = service.get("  shikun &  BINUI ", "", "general")
    assert ran1 and not ran2 and again is first and service.runs == 1
    service.get("Shikun & Binui", "", "negotiation")
    assert service.runs == 2
    assert request_key("A  B", None, "general", "offline_demo") == request_key("a b", "", "general", "offline_demo")


def test_pdf_is_cached_per_run(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    first, _ = service.pdf(r)
    assert service.pdf(r)[0] is first


def test_ambiguous_name_asks_for_domain(service):
    r, _ = service.get("Arup", "", "general")
    assert r["status"] == "clarification_required" and r["briefing"] is None


def test_unknown_company_offline_has_no_sources_and_no_briefing(service):
    r, _ = service.get("Teva Pharmaceutical", "", "general")
    assert r["status"] == "no_briefing" and r["usage"]["model_calls"]["draft"] == 0


def test_unavailable_mode_rejected(service):
    with pytest.raises(ValueError, match="not available"):
        service.get("Arup", "arup.com", "general", mode="live")


# --- PDF (natural pagination, about 10 pt) -------------------------------------------------------------------------

def test_pdf_is_readable_with_required_content(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    data, info = build_pdf(r, GENERATION_LABEL)
    pages, text = pdf_text(data)
    assert 1 <= pages <= 2 and info["pages"] == pages and info["font_size"] >= MIN_FONT  # two pages preferred to one crowded page
    for needed in ("Meeting briefing: Arup", "Purpose: negotiation", "Created:", "SYNTHETIC demonstration records",
                   "1. Company overview", "6. Meeting recommendations", "Sources", "PUBLIC SOURCE",
                   # Arup's 1977/1979 statements were reassessed as a chronological ambiguity, not a contradiction.
                   "Gaps, conflicts and limitations", "Chronological ambiguity", "no AI model used"):
        assert needed in " ".join(text.split()), needed


@pytest.mark.parametrize("language", ["en", "he"])
def test_conflict_sources_are_numbered_in_pdf_sources(service, language):
    # Owner review: the conflict disclosure named NVQ-PUB-005/007, but they were missing from Sources.
    r, _ = service.get("Arup", "arup.com", "negotiation")
    conflict = next(d for d in r["disclosures"] if d["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    data, _ = build_pdf(r, GENERATION_LABEL, language)
    _, text = pdf_text(data)
    flat = " ".join(text.split())
    for eid in conflict["evidence_ids"]:
        assert f"{eid}: PUBLIC SOURCE" in flat, eid  # listed in Sources with its full provenance label
    assert "published unknown" in flat and "1977" in flat and "1979" in flat


def test_conflict_disclosure_line_carries_its_source_numbers(service, monkeypatch):
    from fpdf import FPDF
    sent, original = [], FPDF.multi_cell

    def spy(self, w, h=None, text="", *a, **kw):
        sent.append(text)
        return original(self, w, h, text, *a, **kw)

    monkeypatch.setattr(FPDF, "multi_cell", spy)
    r, _ = service.get("Arup", "arup.com", "negotiation")
    build_pdf(r, GENERATION_LABEL, "en")
    line = next(s for s in sent if "Chronological ambiguity" in s)
    data, _ = build_pdf(r, GENERATION_LABEL, "en")  # the source numbers are printed in their own column
    flat = " ".join(pdf_text(data)[1].split())
    refs = [re.search(rf"\[(\d+)\] {eid}#", flat).group(1) for eid in ("NVQ-PUB-005", "NVQ-PUB-007")]
    assert len(refs) == 2 and all(f"[{n}]" in line for n in refs)


def test_pdf_tags_items_and_origins(service):
    r, _ = service.get("Shikun & Binui", "", "general")
    _, text = pdf_text(build_pdf(r, GENERATION_LABEL)[0])
    assert "[FACT, synthetic]" in text and "[RECOMMENDATION]" in text


def test_long_content_continues_on_more_pages_without_shortening(service):
    # Owner-approved change to FR-09/AT-06 (2026-11-15; type size and pagination revised 2026-11-20): one page is preferred, but when the briefing does not fit on
    # one page at 8 pt it continues on further pages; nothing is shortened or dropped (it used to be shortened).
    r, _ = service.get("Arup", "arup.com", "negotiation")
    big = copy.deepcopy(r)
    for n, (key, items) in enumerate(big["briefing"].items()):
        for m, item in enumerate(items):
            item["text"] = f"Item {n}-{m}: long sentence about document control and transmittals. " * 6
        items.extend([{**copy.deepcopy(i), "text": i["text"].replace("Item ", "Copy ")} for i in items])
    data, info = build_pdf(big)
    pages, text = pdf_text(data)
    flat = " ".join(text.split())
    assert 2 <= pages <= MAX_PAGES and info["pages"] == pages and not info["shortened"]
    assert info["font_size"] >= MIN_FONT
    for items in big["briefing"].values():  # every item is printed in full
        for item in items:
            assert item["text"].split(":")[0] + ":" in flat, item["text"][:12]
    assert f"page 1 of {pages}" in flat and f"page {pages} of {pages}" in flat  # the footer on every page
    assert NOTICE.split(";")[0][:40] in flat  # the synthetic notice is never dropped


def test_disclosures_are_never_dropped_so_extreme_content_reports_overflow(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    huge = copy.deepcopy(r)
    huge["disclosures"] = [{"id": f"gap:{i}", "text": "An important limitation that must stay visible. " * 3}
                           for i in range(200)]  # more than MAX_PAGES pages of disclosures
    with pytest.raises(PdfOverflow):
        build_pdf(huge)


def test_pdf_handles_non_latin_punctuation(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    odd = copy.deepcopy(r)
    odd["briefing"]["meeting_recommendations"][0]["text"] = "Ask about “transmittals” — and costs…"
    pages, text = pdf_text(build_pdf(odd)[0])
    assert pages <= MAX_PAGES and '"transmittals" - and costs...' in text


def test_no_pdf_without_a_briefing():
    with pytest.raises(ValueError):
        build_pdf({"briefing": None})


# --- Streamlit page (headless) ---------------------------------------------------------------

def page(kb, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DEAL_PREP_APP_CHROMA_DIR", str(kb))
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")  # tests never read .env
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return AppTest.from_file(str(APP), default_timeout=120).run()


def button(at, label_start):
    return next(b for b in at.button if b.label.startswith(label_start))


def visible_text(at) -> str:
    parts = [e.value for kind in ("markdown", "caption", "info", "warning", "error", "success", "header", "subheader")
             for e in getattr(at, kind)]
    return " ".join(str(p) for p in parts)


def test_streamlit_page_runs_once_and_reruns_do_not_research_again(kb, monkeypatch):
    at = page(kb, monkeypatch)
    assert not at.exception and at.title[0].value == "Prepare Meeting"
    at.selectbox[0].set_value("Shikun & Binui")
    button(at, "Prepare briefing").click().run()
    assert not at.exception
    assert any("Briefing: Shikun & Binui" in h.value for h in at.header)
    assert at.session_state.service.runs == 1
    at.run()  # an ordinary rerun (e.g. widget interaction)
    button(at, "Prepare briefing").click().run()  # pressing submit again for the same request
    assert at.session_state.service.runs == 1  # cached: no new research
    assert any("saved result" in i.value for i in at.info)


OTHER_OPTION = "Other company (enter name below)"


def test_streamlit_page_shows_clarification_for_ambiguous_name(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value(OTHER_OPTION)
    at.text_input[0].set_value("Arup")
    button(at, "Prepare briefing").click().run()
    assert not at.exception
    assert any("official website domain" in w.value and "ARUP Laboratories" in w.value for w in at.warning)
    assert not any("Briefing:" in h.value for h in at.header)  # nothing is researched for an ambiguous name


# --- Prepare Meeting form: conflicting company inputs (found in the manual Demo 3 walkthrough, 9 November 2026) ---

def test_other_company_option_is_plain_text_so_typing_finds_it(kb, monkeypatch):
    at = page(kb, monkeypatch)
    options = at.selectbox[0].options
    assert OTHER_OPTION in options and not any("…" in o for o in options)
    assert [o for o in options if o.casefold().startswith("other company")] == [OTHER_OPTION]


def test_listed_company_with_a_typed_name_warns_and_runs_nothing(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Arup")
    at.text_input[0].set_value("Arup")
    button(at, "Prepare briefing").click().run()
    assert not at.exception and at.session_state.service.runs == 0
    assert any("Company is set to “Arup”" in w.value and "(“Arup”)" in w.value and "No research was run" in w.value
               for w in at.warning)
    assert not any("Briefing:" in h.value for h in at.header)


def test_conflicting_input_never_shows_an_earlier_cached_briefing(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Arup")
    button(at, "Prepare briefing").click().run()
    assert at.session_state.service.runs == 1 and any("Briefing: Arup" in h.value for h in at.header)
    at.text_input[0].set_value("Arup")  # same listed company, now with a conflicting typed name
    button(at, "Prepare briefing").click().run()
    assert at.session_state.service.runs == 1  # no new research
    assert any("Company is set to “Arup”" in w.value for w in at.warning)
    assert not any("Briefing:" in h.value for h in at.header)  # the earlier result is not shown as an answer
    assert not any("Showing the saved result" in i.value for i in at.info)


def test_whitespace_only_name_does_not_conflict_with_a_listed_company(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Ashtrom Group")
    at.text_input[0].set_value("   ")
    button(at, "Prepare briefing").click().run()
    assert not at.exception and at.session_state.service.runs == 1
    assert any("Briefing: Ashtrom Group" in h.value for h in at.header)
    assert not any("Company is set to" in w.value for w in at.warning)


def test_other_company_with_whitespace_only_name_asks_for_a_name(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value(OTHER_OPTION)
    at.text_input[0].set_value("   ")
    button(at, "Prepare briefing").click().run()
    assert not at.exception and at.session_state.service.runs == 0
    assert any("Please enter a company name" in e.value for e in at.error)


def test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Arup")  # demo company with its official domain preset
    button(at, "Prepare briefing").click().run()
    assert not at.exception and any("Briefing: Arup" in h.value for h in at.header)
    subheaders = [s.value for s in at.subheader]
    assert subheaders == list(SECTION_TITLES.values())
    text = visible_text(at)
    assert ":blue-background[PUBLIC SOURCE]" in text and ":orange-background[SYNTHETIC]" in text
    assert "Download PDF (English)" in [b.label for b in at.get("download_button")]


def test_streamlit_language_switch_rerenders_pdf_without_new_research(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Shikun & Binui")
    button(at, "Prepare briefing").click().run()
    at.radio[0].set_value("he").run()
    assert not at.exception and at.session_state.service.runs == 1
    assert "Download PDF (Hebrew)" in [b.label for b in at.get("download_button")]


def test_streamlit_loads_saved_demo_without_research(kb, monkeypatch):
    at = page(kb, monkeypatch)
    button(at, "Load saved demonstration briefing").click().run()
    assert not at.exception and at.session_state.service.runs == 0
    saved = load_saved_demo()
    assert any("SIMULATED saved demonstration" in w.value and saved["created_at"][:16].replace("T", " ") in w.value
               for w in at.warning)
    assert any(f"Briefing: {saved['identity']['name']}" in h.value for h in at.header)


def test_research_status_panel_states_the_actual_reason_news_was_not_run(kb, monkeypatch):
    """Portfolio Phase 3 Task 1: the panel repeats the reason recorded in the trace, not a fixed offline text."""
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Ashtrom Group")
    button(at, "Prepare briefing").click().run()
    assert not at.exception
    assert "News search: not run (live news is disabled in offline demo mode)" in visible_text(at)


def test_user_facing_text_has_no_internal_codes(kb, monkeypatch):
    at = page(kb, monkeypatch)
    at.selectbox[0].set_value("Arup")
    button(at, "Prepare briefing").click().run()
    text = visible_text(at)
    for code in ("provider_error", "budget_exhausted", "partial_internal_only", "external_with_internal_gap",
                 "insufficient_sources", "status=", "TransportError"):
        assert code not in text, code


# --- Hebrew PDF -------------------------------------------------------------------------------

def test_hebrew_pdf_has_hebrew_text(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    data, info = build_pdf(r, GENERATION_LABEL, "he")
    pages, text = pdf_text(data)
    assert 1 <= pages <= 2 and info["language"] == "he" and info["font_size"] >= MIN_FONT
    for word in ("תדריך", "סקירת", "המלצות", "מקורות", "פערים", "סינתטיות"):
        assert word in text, word
    assert "Arup" in text and "PUBLIC SOURCE" in text  # mixed-direction content survives


def test_hebrew_identifiers_are_forced_left_to_right(service, monkeypatch):
    # Found in the live test: run ID 58aed862a473 rendered as 473a862aed58 inside a Hebrew line.
    from fpdf import FPDF
    sent = []
    original = FPDF.multi_cell

    def spy(self, w, h=None, text="", *a, **kw):
        sent.append(text)
        return original(self, w, h, text, *a, **kw)

    monkeypatch.setattr(FPDF, "multi_cell", spy)
    r = copy.deepcopy(load_saved_demo())
    r["run_id"] = "58aed862a473"
    build_pdf(r, "", "he")
    meta = next(s for s in sent if "58aed862a473" in s)
    assert "⁦" + "58aed862a473" + "⁩" in meta  # LRI ... PDI around the identifier
    assert any("⁦" in s and "UTC" in s for s in sent)  # dates too
    note = next(s for s in sent if "שפת המקור" in s)
    assert "לא מקוון" not in note  # no false "offline / no model" claim in live mode


def test_hebrew_pdf_cached_separately_from_english(service):
    r, _ = service.get("Ashtrom Group", "", "introduction")
    en, he = service.pdf(r, "en")[0], service.pdf(r, "he")[0]
    assert en != he and service.pdf(r, "he")[0] is he


def test_hebrew_pdf_reports_missing_font_clearly(service, tmp_path, monkeypatch):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    monkeypatch.setenv("DEAL_PREP_FONT_DIR", str(tmp_path))
    with pytest.raises(HebrewFontMissing, match="Hebrew glyphs"):
        build_pdf(r, "", "he")


def test_unknown_pdf_language_rejected(service):
    r, _ = service.get("Arup", "arup.com", "negotiation")
    with pytest.raises(ValueError, match="language"):
        build_pdf(r, "", "fr")


# --- saved demonstration ------------------------------------------------------------------------

def test_saved_demo_keeps_original_date_and_simulated_label(service):
    saved = load_saved_demo()
    assert saved["saved_demo"] is True and saved["mode_label"].startswith("SIMULATED")
    assert saved["status"] in ("briefing_ready", "partial_briefing") and saved["briefing"]
    for lang, phrase in (("en", "SIMULATED SAVED DEMONSTRATION"), ("he", "SIMULATED")):
        _, text = pdf_text(service.pdf(saved, lang)[0])
        assert phrase in " ".join(text.split())
    _, text = pdf_text(service.pdf(saved, "en")[0])
    original = datetime.fromisoformat(saved["created_at"]).strftime("%d %b %Y %H:%M UTC")
    assert f"created {original}" in " ".join(text.split())
    assert service.runs == 0  # loading and exporting never researched


def test_save_and_load_round_trip_never_redates(service, tmp_path):
    r, _ = service.get("Shikun & Binui", "", "general")
    path = save_demo(r, tmp_path / "demo.json")
    loaded = load_saved_demo(path)
    assert loaded["created_at"] == r["created_at"] and loaded["run_id"] == r["run_id"] and loaded["saved_demo"]


def test_only_real_briefings_can_be_saved_and_loaded(service, tmp_path):
    none, _ = service.get("Teva Pharmaceutical", "", "general")
    with pytest.raises(ValueError, match="only a produced briefing"):
        save_demo(none, tmp_path / "x.json")
    (tmp_path / "plain.json").write_text('{"status": "briefing_ready"}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a saved demonstration"):
        load_saved_demo(tmp_path / "plain.json")
