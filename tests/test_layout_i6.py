"""Phase 4.5 I6, Phase 1: PDF sources grouped by document, explained empty sections, briefing-shape measurements.

No index, no embedding model, no network: results and bundles here are small synthetic dicts. Company and document
names are invented for these tests (no benchmark or demo company).
"""
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pypdf import PdfReader

from deal_prep import pipeline
from deal_prep.briefing import _section_notes, draft_briefing
from deal_prep.demo import TemplateDrafter
from deal_prep.disclosures import required_disclosures
from deal_prep.pdf_export import _source_numbers, build_pdf, source_groups
from deal_prep.web_research import Budget, SearchConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import briefing_shape as shape  # noqa: E402

PUB = "PUBLIC SOURCE | Testco Haulage | https://testco.example/about"
SYN = "SYNTHETIC - not a real business fact | Example vendor"


def flat(data: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(data))
    return len(reader.pages), " ".join(" ".join(p.extract_text() for p in reader.pages).split())


def result(briefing: dict, disclosures=(), evidence=None, notes=None) -> dict:
    sections = {k: [] for k in ("company_overview", "recent_developments", "our_relationship", "opportunities",
                                "competitive_positioning", "meeting_recommendations")}
    sections.update(briefing)
    return {"created_at": "2026-11-09T09:00:00+00:00", "identity": {"name": "Testco Haulage"},
            "company_input": "Testco Haulage", "labels": {}, "purpose": "negotiation", "run_id": "t-1",
            "briefing": sections, "disclosures": list(disclosures), "section_notes": notes or {},
            "evidence": evidence or {}}


def fact(text, *ids, claim="real_world_fact"):
    return {"kind": "fact", "text": text, "evidence_ids": list(ids), "claim_type": claim}


EVIDENCE = {**{f"PUB-TST-001#{n}": {"info_origin": "public_source", "provenance_label": PUB} for n in range(4)},
            "PRC-TST-2026#2": {"info_origin": "synthetic_record", "provenance_label": SYN},
            "PRC-TST-2026#4": {"info_origin": "synthetic_record", "provenance_label": SYN},
            "WEB-0a1b2c3d": {"info_origin": "public_source", "provenance_label": "PUBLIC SOURCE | news.example"}}


def sample():
    return result({"company_overview": [fact("Testco runs 12 depots.", "PUB-TST-001#2", "PUB-TST-001#0")],
                   "recent_developments": [fact("Testco opened a depot.", "WEB-0a1b2c3d")],
                   "meeting_recommendations": [{"kind": "recommendation", "text": "Compare list prices.",
                                                "evidence_ids": ["PRC-TST-2026#4", "PRC-TST-2026#2",
                                                                 "PUB-TST-001#3"]}]},
                  disclosures=[{"id": "conflict:x", "text": "Sources differ.", "evidence_ids": ["PUB-TST-001#1"]}],
                  evidence=EVIDENCE)


# --- P2: sources grouped by document ---------------------------------------------------------------------

def test_passages_of_one_document_share_one_source_line_in_first_citation_order():
    groups = source_groups(sample())
    assert [(g["document"], g["evidence_ids"]) for g in groups] == [
        ("PUB-TST-001", ["PUB-TST-001#0", "PUB-TST-001#1", "PUB-TST-001#2", "PUB-TST-001#3"]),  # incl. disclosure
        ("WEB-0a1b2c3d", ["WEB-0a1b2c3d"]),
        ("PRC-TST-2026", ["PRC-TST-2026#2", "PRC-TST-2026#4"])]
    numbers = _source_numbers(sample())
    assert numbers["PUB-TST-001#1"] == numbers["PUB-TST-001#3"] == 1 and numbers["PRC-TST-2026#4"] == 3


def test_passages_of_one_document_with_different_labels_stay_separate():
    ev = {"DOC-1#0": {"provenance_label": "label A", "info_origin": "public_source"},
          "DOC-1#1": {"provenance_label": "label B", "info_origin": "public_source"}}
    r = result({"company_overview": [fact("x", "DOC-1#0", "DOC-1#1")]}, evidence=ev)
    assert [g["label"] for g in source_groups(r)] == ["label A", "label B"]


@pytest.mark.parametrize("language", ["en", "he"])
def test_pdf_lists_every_cited_passage_once_per_document(language):
    pages, text = flat(build_pdf(sample(), language=language)[0])
    assert pages == 1
    assert "PUB-TST-001#0, #1, #2, #3" in text and "PRC-TST-2026#2, #4" in text
    assert "WEB-0a1b2c3d: PUBLIC SOURCE" in text  # a single passage keeps its full ID form, as before
    assert "[4]" not in text  # three documents, three numbers (seven passages)


def test_item_refs_name_each_document_once(monkeypatch):
    from fpdf import FPDF
    sent, original = [], FPDF.multi_cell

    def spy(self, w, h=None, text="", *a, **kw):
        sent.append(text)
        return original(self, w, h, text, *a, **kw)

    monkeypatch.setattr(FPDF, "multi_cell", spy)
    build_pdf(sample())
    rec = next(s for s in sent if "Compare list prices." in s)
    assert rec.endswith("Compare list prices. [3][1]")  # price-list document first cited there, then the profile
    assert next(s for s in sent if "Sources differ." in s).endswith("[1]")


# --- P3: empty sections explained ------------------------------------------------------------------------

EMPTY = ("recent_developments", "our_relationship", "opportunities", "competitive_positioning",
         "meeting_recommendations")


def test_section_notes_keep_the_drafters_specific_reason_only():
    draft = {"sections": {"company_overview": [fact("x", "A#0")], "opportunities": [], "competitive_positioning": [],
                          "recent_developments": []},
             "disclosures": [{"id": "empty_section:competitive_positioning",
                              "text": "No competitor is named   in the evidence."},
                             {"id": "empty_section:opportunities", "text": "No supported content for this section."},
                             {"id": "empty_section:recent_developments", "text": "No supported content"},
                             {"id": "empty_section:company_overview", "text": "Not empty, so not a note."},
                             {"id": "empty_section:unknown", "text": "Not a section."},
                             {"id": "gap:1", "text": "A research gap."}]}
    assert _section_notes(draft) == {"competitive_positioning": "No competitor is named in the evidence."}
    long = {"sections": {"opportunities": []}, "disclosures": [{"id": "empty_section:opportunities", "text": "y" * 900}]}
    assert len(_section_notes(long)["opportunities"]) == 300


def bundle():
    """A minimal valid research bundle: one public passage about an invented company."""
    return {"status": "complete", "created_at": "2026-11-09T09:00:00+00:00", "purpose": "general",
            "identity": {"name": "Testco Haulage", "org_id": "testco", "domain": "testco.example"}, "gaps": [],
            "external": {"status": "found_48h", "evidence": []},
            "internal": {"company_profile": {"evidence": [
                {"evidence_id": "PUB-TST-001#0", "document_id": "PUB-TST-001", "info_origin": "public_source",
                 "provenance_label": PUB, "text": "Testco Haulage runs a regional depot network.", "metadata": {}}]}}}


def model_output(notes: dict) -> str:
    sections = {s: [] for s in EMPTY}
    sections["company_overview"] = [fact("Testco Haulage runs a regional depot network.", "PUB-TST-001#0")]
    return json.dumps({"sections": sections,
                       "disclosures": [{"id": f"empty_section:{s}", "text": notes.get(s, "No supported content.")}
                                       for s in EMPTY]})


def test_draft_briefing_returns_the_reason_without_changing_the_disclosures():
    b = bundle()
    out = draft_briefing(b, lambda messages: model_output({"competitive_positioning": "No competitor is named."}))
    assert out["status"] == "ok"
    assert out["section_notes"] == {"competitive_positioning": "No competitor is named."}
    assert out["disclosures"] == required_disclosures(b)  # scored disclosures: unchanged by I6


def test_offline_template_output_carries_no_notes_so_offline_briefings_are_unchanged():
    out = draft_briefing(bundle(), TemplateDrafter())
    assert out["status"] == "ok" and out["section_notes"] == {}


def test_pipeline_result_carries_the_notes(monkeypatch):
    monkeypatch.setattr(pipeline, "gather_research", lambda *a, **kw: bundle())
    r = pipeline.prepare_briefing("Testco Haulage", news_client=None, budget=Budget(SearchConfig()),
                                  generate=lambda m: model_output({"opportunities": "Only existing terms found."}),
                                  now=datetime(2026, 11, 9, 9, tzinfo=timezone.utc))
    assert r["status"] == "briefing_ready" and r["section_notes"] == {"opportunities": "Only existing terms found."}


@pytest.mark.parametrize("language", ["en", "he"])
def test_pdf_shows_the_reason_under_the_empty_heading(language):
    r = result({"company_overview": [fact("Testco runs 12 depots.", "PUB-TST-001#0")]}, evidence=EVIDENCE,
               notes={"competitive_positioning": "No competitor is named in the evidence."})
    pages, text = flat(build_pdf(r, language=language)[0])
    assert pages == 1 and "No competitor is named in the evidence." in text
    if language == "en":
        assert "No supported content: No competitor is named in the evidence." in text
        assert text.count("No supported content (see gaps below).") == 4  # sections without a reason: unchanged


# --- P1: briefing-shape measurements ---------------------------------------------------------------------

def record(briefing, scenario="DEV-X1", drafting_input=None, **extra):
    r = result(briefing, evidence=None)
    return {"scenario": scenario, "purpose": "negotiation", "news_mode": "news_fixture", "status": "briefing_ready",
            "company": "Testco Haulage", "briefing": r["briefing"], "disclosures": [],
            "drafting_input": drafting_input or {}, **extra}


def test_repeated_figures_and_dates_are_found_across_sections_only():
    rec = record({"our_relationship": [fact("Proposal: 180 users at USD 49, valid until 20 December 2026.", "R#0",
                                            claim="relationship")],
                  "meeting_recommendations": [{"kind": "recommendation", "evidence_ids": ["R#0"],
                                               "text": "Hold USD 49 before December 20; it is 2026."}],
                  "company_overview": [fact("Founded in 1998; 180 staff; 49 depots in 2025.", "P#0"),
                                       fact("It has 49 sites.", "P#1")]})
    rep = shape.repeated_across_sections(rec["briefing"])
    assert rep == {"date:20 december": ["our_relationship", "meeting_recommendations"],
                   "figure:180": ["company_overview", "our_relationship"],
                   "figure:49": ["company_overview", "our_relationship", "meeting_recommendations"]}
    assert "figure:2026" not in rep and "figure:1998" not in rep and "figure:20" not in rep  # years and date digits


def test_placement_measures():
    di = {eid: {"source": f"internal:{topic}", "info_origin": "synthetic_record", "provenance_label": SYN}
          for eid, topic in (("R#0", "relationship_history"), ("C#0", "competition"),
                             ("P#0", "vendor_products_pricing"))}
    rec = record({"our_relationship": [fact("x", "R#0", claim="relationship")],
                  "competitive_positioning": [fact("Product capability.", "P#0", claim="vendor_product"),
                                              {"kind": "recommendation", "text": "Battlecard.",
                                               "evidence_ids": ["C#0"]}]}, drafting_input=di)
    m = shape.measure(rec)
    assert m["customer"] and m["empty_opportunities_customer"]
    assert m["competitive_items_without_competitor_evidence"] == ["Product capability."]
    assert m["empty_with_reason"] is None  # record made before I6: reported as n/a, never as 0
    m2 = shape.measure({**rec, "section_notes": {"opportunities": "Only existing terms."}})
    assert m2["empty_with_reason"] == 1
    assert m["pdf"]["font_size"] is not None and m["pdf"]["source_lines_grouped"] <= m["pdf"]["source_lines_per_passage"]


def test_the_body_size_steps_down_only_when_the_pages_do_not_fit(monkeypatch):
    from deal_prep import pdf_export
    from deal_prep.pdf_export import MAX_PAGES
    calls, original = [], pdf_export._render

    def render(result, size, label, lang, total_pages=1):  # signature since 2026-11-20 (natural pagination)
        calls.append(size)
        pdf = original(result, size, label, lang, total_pages)
        if size > 9.0:  # pretend the briefing needs more than MAX_PAGES pages at the larger sizes
            while pdf.page_no() <= MAX_PAGES:
                pdf.add_page()
        return pdf

    monkeypatch.setattr(pdf_export, "_render", render)
    _, info = build_pdf(sample())
    assert calls == [10.0, 9.5, 9.0, 9.0]  # 10, then 9.5, then 9 pt; the last size is rendered twice (page count, footer)
    assert info["font_size"] == 9.0 and info["item_spacing"] is True and info["pages"] == 1


@pytest.mark.parametrize("language", ["en", "he"])
def test_items_are_indented_under_their_heading_and_keep_their_text(language, monkeypatch):
    from fpdf import FPDF
    from deal_prep.pdf_export import INDENT_MM, SOURCE_NUM_MM
    sent, original = [], FPDF.multi_cell

    def spy(self, w, h=None, text="", *a, **kw):
        sent.append((round(self.get_x() - self.l_margin, 2), round(self.epw - w, 2), text, kw.get("align")))
        return original(self, w, h, text, *a, **kw)

    monkeypatch.setattr(FPDF, "multi_cell", spy)
    _, info = build_pdf(sample(), language=language)
    item = next(s for s in sent if "Compare list prices." in s[2])
    assert item[1] == INDENT_MM and item[0] == (0.0 if language == "he" else INDENT_MM)  # Hebrew: indent on the right
    assert item[2].endswith("Compare list prices. [3][1]" + ("⁩" if language == "he" else ""))  # same text
    assert next(s for s in sent if "Sources differ." in s[2])[1] == INDENT_MM  # disclosures too
    heading = next(s for s in sent if "Company overview" in s[2] or "סקירת החברה" in s[2])
    assert heading[:2] == (0.0, 0.0)  # headings keep the full width
    source = next(s for s in sent if "PRC-TST-2026#2, #4" in s[2])
    # English: the number stands in its own column (hanging indent); Hebrew keeps the number in the line
    assert source[1] == INDENT_MM + (0.0 if language == "he" else SOURCE_NUM_MM) and source[3] == ("R" if language == "he" else "L")
    assert info["item_spacing"] is True  # a short briefing keeps the gap between items


# --- Phase 2: section placement and conciseness in the drafting input -------------------------------------

def test_with_i6_off_the_system_rules_are_exactly_the_i5_rules(monkeypatch):
    from deal_prep import briefing, contract
    for old, _ in briefing.I6_CONTRACT_EDITS:
        assert briefing.CONTRACT_RULES.count(old) == 1  # every I6 edit applies, exactly once
    i5 = briefing.SYSTEM_RULES + briefing.CONTRACT_RULES + briefing.I4_RULES + briefing.I5_RULES
    assert briefing.i6_active() and briefing.system_rules() != i5
    assert briefing.system_rules().endswith(briefing.I6_RULES)
    assert "or another allowed section" not in briefing.system_rules()
    monkeypatch.setattr(contract, "LAYOUT_ENABLED", False)
    assert not briefing.i6_active() and briefing.system_rules() == i5


def test_i6_is_active_only_with_i5(monkeypatch):
    from deal_prep import briefing, business
    monkeypatch.setattr(business, "ENABLED", False)
    assert not briefing.i6_active() and "Where things go" not in briefing.system_rules()


ANALYSIS = {
    "price_positions": [{"id": "price_position:1", "status": "calculated", "proposed_price": 49.0, "list_price": 52.0,
                         "currency": "USD", "unit": "per user per month", "discount_pct": 5.769,
                         "discount_display": "5.8%", "approval": {"text": "Within account-executive authority."},
                         "proposal_evidence_id": "PRP#0", "list_evidence_id": "PRC#2"}],
    "requested_additions": [{"id": "requested_addition:1", "status": "calculated", "quantity": 60.0, "unit": "users",
                             "product": "Vault", "display": "USD 3,120 per month", "monthly_at_list": 3120.0,
                             "quantity_after_addition": 240.0, "request_evidence_id": "COR#1",
                             "list_evidence_id": "PRC#2"},
                            {"id": "requested_addition:2", "status": "calculated", "quantity": 8.0, "unit": "TB",
                             "product": "Retention Add-on", "display": "USD 1,920 per month", "monthly_at_list": 1920.0,
                             "request_evidence_id": "COR#2", "list_evidence_id": "PRC#3"}],
    "deadlines": [], "status_checks": [],
    "eligibility": [{"id": "eligibility:1", "capability": "Customer-supplied keys are available to Vault customers.",
                     "available_to": "Vault customers", "marker": "Vault", "triggers": ["customer-supplied"],
                     "evidence_id": "FAQ#3"}]}


def test_layout_changes_only_section_and_wording_never_what_is_measured():
    from deal_prep.contract import business_topics
    i5, i6 = business_topics(ANALYSIS), business_topics(ANALYSIS, layout=True)
    strip = lambda ts: [{k: v for k, v in t.items() if k != "requirement"} for t in ts]  # noqa: E731
    assert strip(i5) == strip(i6)  # same ids, sections, evidence groups, markers and conditions
    req = {t["id"]: t["requirement"] for t in i6}
    assert "State this once, here" in req["price_position:1"] and "not been quoted" in req["requested_addition:1"]
    sections = {t["id"]: t["section"] for t in i6}  # an extension stays with the proposal; a new add-on is an opportunity
    assert sections["requested_addition:1"] == "our_relationship" and sections["requested_addition:2"] == "opportunities"
    assert "in opportunities" in req["requested_addition:2"] and "Do not cite the proposal" in req["requested_addition:2"]
    old = {t["id"]: t["requirement"] for t in i5}["requested_addition:2"]
    assert old.startswith("As analysis: the customer's request for 8 TB") and "opportunities" not in old  # I5 unchanged
    assert "Do not recommend, pitch or plan to demonstrate it" in req["eligibility:1"]
    assert all("State this once" not in t["requirement"] for t in i5)


def test_layout_brief_is_added_to_the_purpose_brief_only_with_i6():
    from deal_prep.contract import LAYOUT_BRIEFS, PURPOSE_BRIEFS, model_contract
    for purpose in ("negotiation", "follow_up", "product_demo", "introduction", "general"):
        off = model_contract({"purpose": purpose}, [])["purpose_brief"]
        on = model_contract({"purpose": purpose}, [], layout=True)["purpose_brief"]
        assert off == PURPOSE_BRIEFS[purpose]
        assert on == off + (" " + LAYOUT_BRIEFS[purpose] if purpose in LAYOUT_BRIEFS else "")


def _contract_payload(sid, monkeypatch, layout):
    import benchmark_harness as h
    from deal_prep import contract

    class Capture:
        def __init__(self):
            self.inner, self.messages = TemplateDrafter(), []

        def __call__(self, messages):
            self.messages.append(messages)
            return self.inner(messages)

    monkeypatch.setattr(contract, "LAYOUT_ENABLED", layout)
    dev = h.compile_split("dev")
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == sid)
    cap = Capture()
    rec = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "i6" / f"{sid}_{layout}", "news_fixture", generate=cap)
    return rec, json.loads(cap.messages[0][1]["content"]), cap.messages[0][0]["content"]


def _tokenized(rec, obj) -> str:
    """Meeting IDs are random per run: compare through their tokens (as benchmark_harness.canonical does)."""
    text = json.dumps(obj, sort_keys=True)
    for tok, real in rec["tokens"].items():
        if tok.startswith("HIST:"):
            text = text.replace(real.split("#")[0], tok)
    return text


@pytest.mark.parametrize("sid", ["DEV-P2", "DEV-M2"])
def test_i6_moves_topics_to_their_home_with_the_same_evidence(sid, monkeypatch):
    import benchmark_harness as h
    rec_on, on, system_on = _contract_payload(sid, monkeypatch, True)
    rec_off, off, system_off = _contract_payload(sid, monkeypatch, False)
    t_on, t_off = on["meeting_contract"]["essential_topics"], off["meeting_contract"]["essential_topics"]
    assert _tokenized(rec_on, [(t["id"], t["evidence_ids"]) for t in t_on]) == \
        _tokenized(rec_off, [(t["id"], t["evidence_ids"]) for t in t_off])
    assert "Where things go" in system_on and "Where things go" not in system_off
    assert rec_on["coverage"]["i6_in_model_input"] is True and rec_off["coverage"]["i6_in_model_input"] is False
    assert h.canonical(rec_on) == h.canonical(rec_off)  # the offline template ignores the drafting rules
    assert rec_on["section_notes"] == {}  # the harness saves the notes (none from the template)
    home = {t["id"].split(":")[0]: t["section"] for t in t_on}
    before = {t["id"].split(":")[0]: t["section"] for t in t_off}
    if sid == "DEV-P2":
        assert before["list_price"] == "meeting_recommendations" and home["list_price"] == "our_relationship"
        assert home["approval_policy"] == before["approval_policy"] == "meeting_recommendations"
    else:
        assert before["demo"] == "opportunities" and home["demo"] == "meeting_recommendations"
        assert "one item per capability area" in on["meeting_contract"]["purpose_brief"]


def test_heldout_records_are_refused(tmp_path):
    held = tmp_path / "heldout_private" / "records.json"
    held.parent.mkdir()
    held.write_text(json.dumps({"records": [record({})]}), encoding="utf-8")
    with pytest.raises(PermissionError):
        shape.load_dev_records(held)
    other = tmp_path / "records.json"
    other.write_text(json.dumps({"records": [record({}, scenario="HX-A1")]}), encoding="utf-8")
    with pytest.raises(PermissionError):
        shape.load_dev_records(other)
