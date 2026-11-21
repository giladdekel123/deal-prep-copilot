"""Portfolio Phase 3, Task 2: readable, relevant offline (template) briefings — GENERAL behaviour.

The offline template copies short passages; it never paraphrases or adds facts. These tests check rules
that must hold for ANY company, not one company's wording:

- R1–R6: no snapshot caveats or internal markers as facts, no email-header items, no table syntax,
  sentence case, meeting headings kept, no mid-phrase truncation.
- F1: every company-overview item names the company, or is a verbatim quote attributed to its publisher.
- F2: each relationship document appears once; an item that only repeats figures already shown says so.
- F3: meeting records are summarised without "…"; task status and due dates only when stored.
- F4: price-list rows are labelled general; anything customer-specific cites this customer's records.
- F5: missing news is explained once; the partial-research disclosure is kept.
- Where retrieved passages cannot support a meaningful item, the item says so.

Scenarios: the three curated companies, a company outside the registry with only an approved meeting
record (limited information), one with no records at all, and fictional documents for a fictional
company (structure supplied with the evidence). Offline only: no paid calls, no credentials.
"""
import io
import json
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from deal_prep import demo
from deal_prep.app_service import SAVED_MODE_LABEL, BriefingService, load_saved_demo
from deal_prep.kb_index import build_kb_index
from deal_prep.pdf_export import build_pdf
from deal_prep.provenance import load_registry

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"
CURATED = [("Shikun & Binui", "", "follow_up"), ("Ashtrom Group", "", "introduction"), ("Arup", "arup.com", "negotiation")]
LIMITED = "Teva Pharmaceutical"  # outside the registry; only an approved (synthetic) meeting record exists
SCENARIOS = [c for c, _, _ in CURATED] + [LIMITED]
REL_PREFIX = "Synthetic demonstration record: "
MEETING_PREFIX = "Past meeting (synthetic user-entered demonstration record, not a verified fact): "
BATTLECARD_PREFIX = "Use the competitor battlecard: "
CUSTOMER_PREFIX = "From this customer's synthetic records: "
GENERAL = re.compile(r"General price list \(not specific to (?P<company>[^)]+)\): ")
INTERNAL_MARKERS = re.compile(r"\[(?:E|C)\d+\]|\((?:E|C)\d+\)|\bC\d+ and C\d+\b|Excerpts >|Claims -|\bLimitations\b")
HEADER_ONLY = re.compile(r"^(?:Subject|From|To|Date):")
NUMBER = re.compile(r"\d[\d,]*\d|\d")
NOT_RETRIEVED = "not among the retrieved records"


@pytest.fixture(scope="module")
def briefings(tmp_path_factory):
    kb = tmp_path_factory.mktemp("readability_kb")
    build_kb_index(chroma_dir=kb)
    service = BriefingService(chroma_dir=kb, history_path=tmp_path_factory.mktemp("rh") / "h.sqlite")
    out = {c: service.get(c, dom, p)[0] for c, dom, p in CURATED}
    cid = service.company_id_for(LIMITED)
    mid = service.add_meeting_draft(cid, "Discussed document control for clinical trial files.", "op-1", "2026-11-03")
    service.approve_meeting(mid, {"summary": "The customer is reviewing document control for trial files.",
                                  "participants": ["Nivarque account executive"],
                                  "concerns": ["Validation effort for regulated records."],
                                  "decisions": ["Share a validation package."]},
                            [{"description": "Send the validation package.", "due_date": "2026-11-20",
                              "op_id": f"{mid}:task:0"}])
    out[LIMITED] = service.get(LIMITED, None, "introduction")[0]
    out["_no_records"] = service.get("Example Logistics Holdings", None, "general")[0]
    return out


def body(text: str) -> str:
    general = GENERAL.match(text)
    if general:
        return text[general.end():]
    for prefix in (REL_PREFIX, MEETING_PREFIX, BATTLECARD_PREFIX, CUSTOMER_PREFIX):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def all_items(r):
    return [(s, item) for s, items in r["briefing"].items() for item in items]


def cited(r, item):
    return [r["evidence"][e]["excerpt"] for e in item["evidence_ids"]]


def table_pairs(excerpt: str) -> dict:
    rows = excerpt.split("Product:", 1)
    if len(rows) < 2 or " | " not in rows[1]:
        return {}
    return dict(p.split(":", 1) for p in ("Product:" + rows[1]).split(" | "))


def draft(evidence, company="Example Engineering Ltd"):
    """Run the template on fictional evidence; structure (doc_type, section, chunk_type) is supplied."""
    rows = [{"conflict_group": None, "approval_status": None, "time_window": None, "provenance_label": "",
             "document_id": e["evidence_id"].split("#")[0], **e} for e in evidence]
    payload = {"company": company, "required_disclosures": [], "evidence": rows}
    return json.loads(demo.TemplateDrafter()([{"role": "system", "content": ""},
                                              {"role": "user", "content": json.dumps(payload)}]))["sections"]


def rel(eid, text, doc_type, section="", chunk_type="paragraph"):
    return {"evidence_id": eid, "source": "internal:relationship_history", "excerpt": text, "doc_type": doc_type,
            "section": section, "chunk_type": chunk_type}


# --- R1–R6 (general, all scenarios) ----------------------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_r1_no_snapshot_limitations_or_internal_markers(briefings, company):
    r = briefings[company]
    for section, item in all_items(r):
        assert not INTERNAL_MARKERS.search(item["text"]), (section, item["text"])
        assert not any(x.startswith("Limitations") for x in cited(r, item)), (section, item["text"])


@pytest.mark.parametrize("company", SCENARIOS)
def test_r2_email_headers_are_never_shown_as_items(briefings, company):
    """A header line may support an item only with its message, or when the item states the message is missing."""
    r = briefings[company]
    for section, item in all_items(r):
        assert not HEADER_ONLY.match(body(item["text"])), (section, item["text"])
        excerpts = cited(r, item)
        if any(HEADER_ONLY.match(x) for x in excerpts):
            assert any(not HEADER_ONLY.match(x) for x in excerpts) or NOT_RETRIEVED in item["text"], item["text"]


@pytest.mark.parametrize("company", SCENARIOS)
def test_r3_no_raw_table_syntax_and_rendered_rows_keep_every_value(briefings, company):
    r = briefings[company]
    for section, item in all_items(r):
        assert " | " not in item["text"] and "Product:" not in item["text"], (section, item["text"])
        if all(table_pairs(x) for x in cited(r, item)):  # the item renders a table row
            for excerpt in cited(r, item):
                for key, value in table_pairs(excerpt).items():
                    assert value.strip() in item["text"], (key, value, item["text"])


def test_r3_table_row_sentence_is_exact():
    text = demo.fact_text("List prices Product: Nivarque Core | Tier: Starter | Unit: per user per month | "
                          "List price (USD): 18 | Minimum term: 12 months", "vendor_product")
    assert text == "Nivarque Core (Starter tier): list price USD 18 per user per month; minimum term 12 months."
    unknown = demo.readable("Service levels Region: EMEA | Support hours: 08:00-18:00 | Response: 4 hours",
                            section="Service levels")
    assert unknown == "Region EMEA; support hours 08:00-18:00; response 4 hours."  # any table, every value kept


@pytest.mark.parametrize("company", SCENARIOS)
def test_r4_every_item_starts_with_a_capital_letter(briefings, company):
    for section, item in all_items(briefings[company]):
        assert body(item["text"])[:1].isupper(), (section, item["text"])


def test_r5_meeting_record_heading_is_kept():
    [item] = draft([{"evidence_id": "HIST-1#0", "source": "internal:meeting_history",
                     "excerpt": "Meeting record (2026-11-02): Pilot agreed. Participants: A. Person"}])["our_relationship"]
    assert item["text"] == MEETING_PREFIX + "Meeting on 2026-11-02: Pilot agreed."


@pytest.mark.parametrize("company", SCENARIOS)
def test_r6_items_are_complete_sentences(briefings, company):
    for section, item in all_items(briefings[company]):
        assert "…" not in item["text"], (section, item["text"])
        assert item["text"].rstrip().rstrip('"').endswith((".", "?", "!")), (section, item["text"])


def test_r6_long_passages_are_cut_at_a_sentence_boundary_and_marked():
    text = demo.fact_text("Discussion First sentence is short. Second sentence " + "word " * 60 + "ends here.",
                          "relationship")
    assert text == REL_PREFIX + "First sentence is short. …"


# --- F1: company references --------------------------------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_f1_overview_items_name_the_company_or_quote_an_attributed_source(briefings, company):
    r = briefings[company]
    org = next((o for o in load_registry().values() if o["name"] == r["identity"]["name"]), {})
    names = [r["identity"]["name"], *org.get("aliases", [])]
    for item in r["briefing"]["company_overview"]:
        if any(n in item["text"] for n in names[:1] + names[1:]) and " states: \"" not in item["text"]:
            continue
        quoted = re.fullmatch(r'(?P<who>.+) states: "(?P<quote>.+)"', item["text"])
        assert quoted, item["text"]
        [ev] = [r["evidence"][e] for e in item["evidence_ids"]]
        publisher = ev["provenance_label"].split(" · ")[1]
        assert quoted["who"] in (publisher, f"{r['identity']['name']}'s own website"), item["text"]
        assert quoted["quote"].rstrip(".") in ev["excerpt"], (quoted["quote"], ev["excerpt"])  # verbatim


def test_f1_attribution_uses_the_publisher_for_any_company():
    sections = draft([{"evidence_id": "PUB-X#1", "source": "internal:company_profile", "doc_type": "public_profile",
                       "section": "Excerpts", "excerpt": 'Excerpts > [E1] "the firm employs about 900 engineers"',
                       "provenance_label": "PUBLIC SOURCE · Wikipedia · https://example.org · published unknown"},
                      {"evidence_id": "PUB-X#2", "source": "internal:company_profile", "doc_type": "public_profile",
                       "section": "Excerpts", "excerpt": 'Excerpts > [E2] "Example Engineering Ltd was founded in 1990"',
                       "provenance_label": "PUBLIC SOURCE · Example Engineering Ltd · https://example.org"}])
    texts = [i["text"] for i in sections["company_overview"]]
    assert texts == ['Wikipedia states: "the firm employs about 900 engineers."',
                     "Example Engineering Ltd was founded in 1990."]


# --- F2: one item per document, no repeated figures -------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_f2_each_document_once_and_repeated_figures_are_not_repeated(briefings, company):
    r = briefings[company]
    shown, docs = set(), []
    for item in r["briefing"]["our_relationship"]:
        docs.append(item["evidence_ids"][0].split("#")[0])
        numbers = set(NUMBER.findall(body(item["text"])))
        if shown and numbers and numbers <= shown:
            assert "restated" in item["text"], item["text"]  # says it repeats, instead of repeating
        assert not re.search(r"(?:^|\. )(?:Thank you|Dear |Kind regards)", body(item["text"])), item["text"]
        shown |= numbers
    assert len(docs) == len(set(docs)), docs


def test_f2_email_restating_known_terms_is_summarised_and_cites_its_header():
    s = draft([rel("PRP-9#1", "Pricing Product: Widget Suite | Quantity: 50 | Unit: per user per month | "
                              "Proposed price (USD): 20 | Valid until: 1 June 2027", "proposal", "Pricing", "table_row"),
               rel("COR-9#0", "From: Vendor sales lead. To: Buyer team. Date: 2 May 2027.", "correspondence"),
               rel("COR-9#1", "Thank you for your time. As discussed, the price of 20 USD for 50 users holds until "
                              "1 June 2027.", "correspondence")])
    proposal, email = s["our_relationship"]
    assert proposal["text"] == REL_PREFIX + ("Widget Suite: 50 users proposed at USD 20 per user per month, valid until "
                                             "1 June 2027.")
    assert email["text"] == REL_PREFIX + "Email of 2 May 2027 (Vendor sales lead to Buyer team): restated the " \
                                         "proposal terms shown above."
    assert email["evidence_ids"] == ["COR-9#0", "COR-9#1"]


def test_f2_email_with_new_content_keeps_it_without_courtesy_phrases():
    [email] = draft([rel("COR-9#0", "From: Vendor sales lead. To: Buyer team. Date: 2 May 2027.", "correspondence"),
                     rel("COR-9#1", "Thank you for meeting us. As agreed, we will run a 30-day pilot.",
                         "correspondence")])["our_relationship"]
    assert email["text"] == REL_PREFIX + "Email of 2 May 2027 (Vendor sales lead to Buyer team): We will run a " \
                                         "30-day pilot."


def test_f2_header_only_email_discloses_that_its_content_was_not_retrieved():
    [email] = draft([rel("COR-9#0", "From: Vendor sales lead. To: Buyer team. Date: 2 May 2027.",
                         "correspondence")])["our_relationship"]
    assert email["text"] == REL_PREFIX + f"Email of 2 May 2027 (Vendor sales lead to Buyer team): its content was {NOT_RETRIEVED}."


def test_f2_meeting_notes_use_their_date_and_section_labels():
    s = draft([rel("MTG-9#0", "Meeting Date: 3 March 2027. Participants: two people.", "meeting_notes", "Meeting"),
               rel("MTG-9#1", "Discussion The buyer asked about archive migration.", "meeting_notes", "Discussion")])
    assert s["our_relationship"][0]["text"] == REL_PREFIX + ("Meeting on 3 March 2027. Discussion: The buyer asked "
                                                             "about archive migration.")
    [only_date] = draft([rel("MTG-9#0", "Meeting Date: 3 March 2027. Participants: two people.", "meeting_notes",
                             "Meeting")])["our_relationship"]
    assert only_date["text"] == REL_PREFIX + f"Meeting on 3 March 2027: its discussion was {NOT_RETRIEVED}."


# --- F3: meeting records --------------------------------------------------------------------------------

@pytest.mark.parametrize("company", ["Shikun & Binui", LIMITED])
def test_f3_meeting_records_are_summarised_without_truncation(briefings, company):
    r = briefings[company]
    meetings = [i for i in r["briefing"]["our_relationship"] if i["claim_type"] == "meeting_history"]
    if company == "Shikun & Binui":
        assert not meetings  # no approved meeting in this scenario: nothing is invented
        return
    [item] = meetings
    assert item["text"].startswith(MEETING_PREFIX + "Meeting on 2026-11-03: ")
    assert "…" not in item["text"] and "Participants" not in item["text"]
    assert "Concerns: Validation effort for regulated records." in item["text"]
    assert "Follow-up task: Send the validation package (Open, due 2026-11-20)." in item["text"]


def test_f3_task_details_only_when_stored_and_cut_records_say_so():
    s = draft([{"evidence_id": "HIST-1#0", "source": "internal:meeting_history",
                "excerpt": "Meeting record (2026-11-06): Pilot agreed. Follow-up task (Open, due not confirmed "
                           "('next week')): Schedule a security review."},
               {"evidence_id": "HIST-2#0", "source": "internal:meeting_history",
                "excerpt": "Meeting record (2026-11-06): Pilot agreed. Decisions: Run a pilot. Follow-up task "
                           "(In Progress, due 2026-11-12): Prepare the …"}])
    first, second = s["our_relationship"]
    assert first["text"] == MEETING_PREFIX + ("Meeting on 2026-11-06: Pilot agreed. Follow-up task: Schedule a "
                                              "security review (Open, due date not confirmed).")
    assert second["text"] == MEETING_PREFIX + ("Meeting on 2026-11-06: Pilot agreed. Decisions: Run a pilot. Later "
                                               "details of this record were not in the retrieved excerpt.")


# --- F4: general vendor information versus customer-specific opportunities -----------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_f4_general_prices_are_labelled_and_customer_items_cite_customer_records(briefings, company):
    r = briefings[company]
    for item in r["briefing"]["opportunities"]:
        sources = {r["evidence"][e]["source"] for e in item["evidence_ids"]}
        general = GENERAL.match(item["text"])
        if sources == {"internal:vendor_products_pricing"}:
            assert general and general["company"] == r["identity"]["name"], item["text"]
        else:
            assert item["text"].startswith(CUSTOMER_PREFIX), item["text"]
            assert sources <= {"internal:relationship_history", "internal:meeting_history"}, sources
            assert all(r["evidence"][e]["info_origin"] == "synthetic_record" for e in item["evidence_ids"])


def test_f4_only_a_proposal_with_a_recorded_status_becomes_a_customer_item():
    row = rel("PRP-9#1", "Pricing Product: Widget Suite | Quantity: 50 | Unit: per user per month | "
                         "Proposed price (USD): 20", "proposal", "Pricing", "table_row")
    status = rel("PRP-9#0", "Scope The proposal was sent on 4 April 2027 and is awaiting approval.", "proposal", "Scope")
    with_status = draft([status, row])
    # The status is copied from the record; the template does not add its own judgement such as "open".
    assert with_status["opportunities"][0]["text"] == (CUSTOMER_PREFIX + "Proposal for Widget Suite. The proposal "
                                                       "was sent on 4 April 2027 and is awaiting approval.")
    assert not any("open" in i["text"].lower() for i in with_status["meeting_recommendations"])
    assert with_status["opportunities"][0]["evidence_ids"] == ["PRP-9#0", "PRP-9#1"]
    without = draft([row])
    assert without["opportunities"] == []  # terms alone do not show an open opportunity
    assert any("Review the synthetic relationship records" in i["text"] for i in without["meeting_recommendations"])


# --- F5: missing news ------------------------------------------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_f5_missing_news_is_explained_once_and_the_partial_disclosure_is_kept(briefings, company):
    r = briefings[company]
    news_lines = [d["text"] for d in r["disclosures"] if "news" in d["text"].lower()]
    assert len(news_lines) == 1 and "does not include current market intelligence" in news_lines[0], news_lines
    assert "not searched" in news_lines[0]
    assert not any("not included in this briefing" in i["text"] for i in r["briefing"]["meeting_recommendations"])


# --- limited and missing information -----------------------------------------------------------------

def test_limited_information_company_gets_an_honest_partial_briefing(briefings):
    r = briefings[LIMITED]
    assert r["status"] == "partial_briefing"
    assert r["briefing"]["company_overview"] == []  # no public snapshot: nothing is invented
    assert [i["claim_type"] for i in r["briefing"]["our_relationship"]] == ["meeting_history"]
    assert all(GENERAL.match(i["text"]) for i in r["briefing"]["opportunities"])


def test_company_without_any_records_gets_no_briefing(briefings):
    r = briefings["_no_records"]
    assert r["status"] == "no_briefing" and "Not enough reliable sources" in r["message"]
    assert not any((r.get("briefing") or {}).values())  # nothing is invented
    assert PROFILE_GAP not in r["message"]  # already covered by "No internal records…": not said twice


# --- missing curated company profile (shared research rule, all modes) --------------------------------

PROFILE_GAP = ("No curated public company profile was retrieved for this briefing. Company information may be "
               "incomplete; any facts included must be supported by other cited sources.")


@pytest.mark.parametrize("company", [c for c, _, _ in CURATED])
def test_no_profile_gap_when_a_curated_profile_was_retrieved(briefings, company):
    assert PROFILE_GAP not in [d["text"] for d in briefings[company]["disclosures"]]


def test_profile_gap_offline_without_other_public_sources(briefings):
    r = briefings[LIMITED]  # outside the registry, one approved meeting record, no news offline
    assert PROFILE_GAP in [d["text"] for d in r["disclosures"]]
    assert r["briefing"]["company_overview"] == [] and r["briefing"]["recent_developments"] == []


def test_profile_gap_for_a_registered_company_whose_profile_was_not_retrieved(tmp_path_factory, monkeypatch):
    from deal_prep import orchestrator
    original = orchestrator._run_internal

    def without_profile(topic, identity, k, chroma_dir):
        results, trace = original(topic, identity, k, chroma_dir)
        return ([], trace) if topic["topic"] == "company_profile" else (results, trace)

    monkeypatch.setattr(orchestrator, "_run_internal", without_profile)
    kb = tmp_path_factory.mktemp("noprofile_kb")
    build_kb_index(chroma_dir=kb)
    r, _ = BriefingService(chroma_dir=kb, history_path=kb / "h.sqlite").get("Arup", "arup.com", "negotiation")
    assert PROFILE_GAP in [d["text"] for d in r["disclosures"]]
    assert r["status"] == "partial_briefing" and r["briefing"]["our_relationship"]  # other records still used


def test_profile_gap_with_live_news_does_not_suppress_news_facts(tmp_path_factory):
    """Live AI + live news (simulated OpenAI and Tavily): the disclosure is added, and a fact supported by a
    cited news source is still included."""
    from datetime import datetime, timedelta, timezone

    from deal_prep.spend import SpendGuard
    from deal_prep.web_research import Budget, SearchConfig, TavilyClient
    from test_llm import simulated_openai

    kb = tmp_path_factory.mktemp("profile_news_kb")
    build_kb_index(chroma_dir=kb)
    service = BriefingService(chroma_dir=kb, history_path=kb / "h.sqlite")
    cid = service.company_id_for(LIMITED)
    mid = service.add_meeting_draft(cid, "Discussed trial-file document control.", "op-1", "2026-11-03")
    service.approve_meeting(mid, {"summary": "The customer is reviewing document control for trial files."})
    when = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    reply = {"results": [{"url": "https://news.example.com/item", "title": f"{LIMITED} opens a new research site",
                          "content": f"{LIMITED} opens a new research site.", "score": 0.9, "published_date": when}]}
    news = TavilyClient("tvly-TEST-NOT-REAL", post=lambda url, json, headers, timeout: reply,
                        config=SearchConfig(max_retries=0))
    r = service._run_live(LIMITED, None, "introduction", client=simulated_openai(),
                          guard=SpendGuard(ledger_path=kb / "openai.json"), news_client=news,
                          budget=Budget(SearchConfig()), history_search=service.history_search(cid))
    assert PROFILE_GAP in [d["text"] for d in r["disclosures"]]
    recent = r["briefing"]["recent_developments"]
    assert recent and all(r["evidence"][e]["info_origin"] == "public_source" for i in recent for e in i["evidence_ids"])
    assert any(LIMITED in i["text"] for i in recent)  # the news-supported fact is kept, not suppressed


# --- proposal status wording -----------------------------------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_proposals_are_not_called_open_unless_the_source_says_so(briefings, company):
    r = briefings[company]
    for section, item in all_items(r):
        if re.search(r"\bopen\b", item["text"], re.I):
            assert any(re.search(r"\bopen\b", x, re.I) for x in cited(r, item)), (section, item["text"])


# --- faithfulness, labels, PDFs and generality -------------------------------------------------------------

@pytest.mark.parametrize("company", SCENARIOS)
def test_every_number_in_an_item_appears_in_its_cited_passages(briefings, company):
    r = briefings[company]
    for section, item in all_items(r):
        source = " ".join(cited(r, item))
        for n in NUMBER.findall(body(item["text"])):
            assert n in source, (section, n, item["text"])


@pytest.mark.parametrize("company", SCENARIOS)
def test_labels_claim_types_and_readable_pdfs(briefings, company):
    r = briefings[company]
    assert r["status"] == "partial_briefing"
    origins = {"real_world_fact": "public_source", "relationship": "synthetic_record",
               "meeting_history": "synthetic_record", "vendor_product": "synthetic_record"}
    for section, item in all_items(r):
        if item["kind"] == "fact":
            assert {r["evidence"][e]["info_origin"] for e in item["evidence_ids"]} == {origins[item["claim_type"]]}
    assert all(i["text"].startswith((REL_PREFIX, MEETING_PREFIX)) for i in r["briefing"]["our_relationship"])
    for lang in ("en", "he"):
        data, _ = build_pdf(r, demo.GENERATION_LABEL, lang)
        assert 1 <= len(PdfReader(io.BytesIO(data)).pages) <= 2, lang  # natural pagination at about 10 pt (2026-11-20)


def test_template_code_names_no_organization():
    """General rules only: the template must not special-case any organization in the registry."""
    source = (ROOT / "src" / "deal_prep" / "demo.py").read_text(encoding="utf-8").casefold()
    for org in load_registry().values():
        for name in [org["name"], *org.get("aliases", [])]:
            assert name.casefold() not in source, name


# --- saved SIMULATED demonstration: re-composed by the shared logic from its stored evidence only --------

def _recompose():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reformat_saved_demo", ROOT / "scripts" / "reformat_saved_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.recompose


def test_saved_demo_keeps_identity_date_and_stored_evidence():
    saved = load_saved_demo()
    assert saved["saved_demo"] is True and saved["mode_label"] == SAVED_MODE_LABEL
    assert saved["created_at"] == "2026-11-06T08:03:56.463045+00:00" and saved["status"] == "partial_briefing"
    assert len(saved["evidence"]) == 19 and sorted(saved["evidence"]) == sorted(saved["evidence_ids"])
    for section, item in all_items(saved):  # every citation is stored evidence, with the origin its claim needs
        for e in item["evidence_ids"]:
            assert e in saved["evidence"], (section, e)
    assert all(i["text"].startswith(REL_PREFIX) for i in saved["briefing"]["our_relationship"])


def test_saved_demo_is_exactly_the_shared_template_output_for_its_stored_evidence():
    """No hand-tailoring: re-running the shared logic over the stored evidence reproduces the saved text."""
    saved = load_saved_demo()
    again = _recompose()(json.loads(json.dumps(saved)))
    assert again["briefing"] == saved["briefing"] and again["disclosures"] == saved["disclosures"]
    for section, item in all_items(saved):
        assert " | " not in item["text"] and not INTERNAL_MARKERS.search(item["text"]), item["text"]
        assert not HEADER_ONLY.match(body(item["text"])) and body(item["text"])[:1].isupper(), item["text"]
    assert [d["id"] for d in saved["disclosures"]] == ["status"]  # the news reason is given once (F5)


def test_saved_demo_says_it_was_recomposed_not_researched(monkeypatch, tmp_path):
    saved = load_saved_demo()
    assert "by the current offline template from the same stored evidence; not newly researched" in \
        saved["generation_label"]
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DEAL_PREP_APP_CHROMA_DIR", str(tmp_path))
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    next(b for b in at.button if b.label.startswith("Load saved demonstration briefing")).click().run()
    assert any("Re-composed" in w.value and "not newly researched" in w.value for w in at.warning)
