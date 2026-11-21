"""C4.3 (owner-approved 2026-11-17): a conflict is disclosed only when it is relevant to the briefing: a retrieved
passage states one side, or the conflict's subject appears in the organization's approved records. Passages of both
conflicting documents on other subjects no longer trigger it. Safety rule: if the final briefing mentions the subject
of a conflict that was set aside, the disclosure is added, with both sides; one side is never shown alone. Uses the
kb_v1 index and its curated SCIM conflict (C2: NVQ-PRD-001 against NVQ-POL-002); simulated model output only."""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep import disclosures, orchestrator
from deal_prep.briefing import draft_briefing
from deal_prep.disclosures import mentioned_conflicts, required_disclosures, set_aside_conflicts, unresolved_conflicts
from deal_prep.kb_index import build_kb_index, load_kb_chunks, to_evidence
from deal_prep.orchestrator import gather_research
from deal_prep.provenance import load_registry
from deal_prep.web_research import Budget, SearchConfig, TavilyClient

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
CHUNKS = {c["chunk_id"]: c for c in load_kb_chunks()}
REGISTRY = load_registry()
SCIM_A = "SCIM user provisioning is available on the Enterprise tier only."
SCIM_B = "SCIM user provisioning is available on the Business and Enterprise tiers."


class FakeTransport:
    def __init__(self, *responses):
        self.queue = list(responses)

    def __call__(self, url, json, headers, timeout):
        return self.queue.pop(0)


def news(company):
    when = (NOW - timedelta(hours=6)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {"results": [{"url": "https://news.example.com/a", "title": f"{company} wins design contract",
                         "content": "...", "score": 0.9, "published_date": when}]}


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("relevance_kb")
    build_kb_index(chroma_dir=d)
    return d


@pytest.fixture(scope="module")
def arup(kb):
    config = SearchConfig()
    client = TavilyClient("test-key-not-real", post=FakeTransport(news("Arup")), config=config)
    return gather_research("Arup", news_client=client, budget=Budget(config), domain="arup.com", chroma_dir=kb,
                           now=NOW)


def chunk(doc_id, contains):
    cid, c = next((cid, c) for cid, c in CHUNKS.items()
                  if c["metadata"]["document_id"] == doc_id and contains in c["text"])
    return {**to_evidence(cid, c["text"], c["metadata"], REGISTRY), "_tool": "search_internal"}


def with_passages(bundle, *passages, record=None, status="approved"):
    b = copy.deepcopy(bundle)
    b.setdefault("supplemental", []).extend(passages)
    if record:  # an approved (or draft) record of this customer stating the text
        meta = {"doc_type": "correspondence", "approval_status": status, "customer_org_id": "arup",
                "document_id": "NVQ-COR-X", "conflict_group": "", "scope": "company"}
        b["internal"]["relationship_history"]["evidence"].append(
            {"evidence_id": "NVQ-COR-X#1", "document_id": "NVQ-COR-X", "info_origin": "synthetic_record",
             "text": record, "metadata": meta, "provenance_label": "SYNTHETIC RECORD · NVQ-COR-X"})
    return b


def unrelated_both(arup):  # one passage of each conflicting document, neither about SCIM
    return with_passages(arup, chunk("NVQ-PRD-001", "Deployment"), chunk("NVQ-POL-002", "Where is customer data"))


def test_the_arup_bundle_has_no_scim_conflict_to_begin_with(arup):
    assert "C2" not in unresolved_conflicts(arup, NOW.date()) and "C2" not in set_aside_conflicts(arup, NOW.date())


def test_unrelated_passages_of_both_documents_no_longer_trigger_the_disclosure(arup):
    b = unrelated_both(arup)
    assert "C2" not in unresolved_conflicts(b, NOW.date()) and "C2" in set_aside_conflicts(b, NOW.date())
    assert not any(d["id"] == "conflict:C2" for d in required_disclosures(b))
    assert "C2" in disclosures._unresolved(b, NOW.date())  # the document-level rule would have disclosed it


def test_a_retrieved_statement_of_one_side_keeps_the_disclosure_with_both_sides(arup, kb):
    b = with_passages(arup, chunk("NVQ-PRD-001", "Enterprise tier only"), chunk("NVQ-POL-002", "Where is customer"))
    assert "C2" in unresolved_conflicts(b, NOW.date())
    orchestrator.add_conflict_sources(b, kb, NOW)  # the other side's statement is fetched
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:C2")
    assert SCIM_A in d["text"] and SCIM_B in d["text"]


def test_the_subject_in_an_approved_record_keeps_the_disclosure_with_both_sides(arup, kb):
    b = unrelated_both(arup)
    b = with_passages(b, record="Is SCIM provisioning included in Core Business?")
    assert "C2" in unresolved_conflicts(b, NOW.date())
    orchestrator.add_conflict_sources(b, kb, NOW)
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:C2")
    assert SCIM_A in d["text"] and SCIM_B in d["text"]


@pytest.mark.parametrize("record, status", [
    ("Is SCIM provisioning included in Core Business?", "draft"),   # a draft note never counts
    ("Please send a revised quote for the Business tier.", "approved"),  # product and tier words are not the subject
    ("Can documents be hosted in Australia?", "approved"),          # another subject
])
def test_records_that_do_not_raise_the_subject_keep_it_set_aside(arup, record, status):
    b = with_passages(unrelated_both(arup), record=record, status=status)
    assert "C2" not in unresolved_conflicts(b, NOW.date()) and "C2" in set_aside_conflicts(b, NOW.date())


def test_a_conflict_without_recorded_statements_cannot_be_judged_and_stays_disclosed(monkeypatch):
    b = {"internal": {"x": {"evidence": [
        {"evidence_id": "A#1", "document_id": "A", "info_origin": "synthetic_record", "text": "a",
         "metadata": {"conflict_group": "X"}},
        {"evidence_id": "B#1", "document_id": "B", "info_origin": "synthetic_record", "text": "b",
         "metadata": {"conflict_group": "X"}}]}}, "identity": {"name": "Acme"}}
    monkeypatch.setattr(disclosures, "_unresolved", lambda bundle, as_of: {"X": ["A", "B"]})
    monkeypatch.setattr(disclosures, "load_manifest", lambda: [{"document_id": "A"}, {"document_id": "B"}])
    assert disclosures.unresolved_conflicts(b, NOW.date()) == {"X": ["A", "B"]}


# --- the safety rule ---------------------------------------------------------------------------------------------

def rec(text):
    return {"kind": "recommendation", "text": text, "evidence_ids": [], "claim_type": None}


def test_a_briefing_that_mentions_a_set_aside_subject_gets_the_disclosure_with_both_sides(arup):
    b = unrelated_both(arup)
    mentions = {"sections": {"meeting_recommendations": [rec("Ask whether SCIM provisioning is needed for all "
                                                             "users.")]}}
    [d] = mentioned_conflicts(b, mentions)
    assert d["id"] == "conflict:C2" and [e.split("#")[0] for e in d["evidence_ids"]] == ["NVQ-POL-002", "NVQ-PRD-001"]
    silent = {"sections": {"meeting_recommendations": [rec("Ask where documents should be hosted.")]}}
    assert mentioned_conflicts(b, silent) == []


def test_the_safety_rule_runs_on_the_final_briefing(arup):
    b = unrelated_both(arup)
    web = b["external"]["evidence"][0]["evidence_id"]
    ok = [e["evidence_id"] for e in b["internal"]["company_profile"]["evidence"]
          if e["metadata"]["approval_status"] == "approved" and not e["metadata"].get("conflict_group")][0]
    record = next(e["evidence_id"] for e in b["internal"]["relationship_history"]["evidence"]
                  if e["metadata"]["approval_status"] == "approved" and not e["metadata"].get("conflict_group"))

    def draft(recommendation):
        return {"sections": {
            "company_overview": [{"kind": "fact", "text": "Arup is an engineering firm.", "evidence_ids": [ok],
                                  "claim_type": "real_world_fact"}],
            "recent_developments": [{"kind": "fact", "text": "Arup won a design contract.", "evidence_ids": [web],
                                     "claim_type": "real_world_fact"}],
            "our_relationship": [{"kind": "fact", "text": "Synthetic record: negotiation in progress.",
                                  "evidence_ids": [record], "claim_type": "relationship"}],
            "opportunities": [{"kind": "inference", "text": "Drawing control may matter.", "evidence_ids": [web]}],
            "competitive_positioning": [rec("Compare total cost.")],
            "meeting_recommendations": [rec(recommendation)]},
            "disclosures": [{"id": d["id"], "text": d["text"]} for d in required_disclosures(b)]}
    for text, expected in (("Ask whether SCIM provisioning is included.", True), ("Confirm the user count.", False)):
        out = draft_briefing(b, lambda messages, d=draft(text): json.dumps(d))
        assert out["status"] == "ok", out.get("error")
        assert any(x["id"] == "conflict:C2" for x in out["disclosures"]) is expected, text


# --- D2 (owner-approved 2026-11-18): conflict safety before the final validation ----------------------------------

def fact(text, evidence_ids, claim_type="vendor_product"):
    return {"kind": "fact", "text": text, "evidence_ids": evidence_ids, "claim_type": claim_type}


def issues_of(bundle, item, section="opportunities"):
    from deal_prep.citations import validate_citations
    draft = {"sections": {section: [item]}, "disclosures": []}
    return [x for x in validate_citations(draft, bundle)["issues"] if x["code"] == "one_sided_conflict_claim"]


def passage_id(bundle, doc_id, contains):
    return next(e["evidence_id"] for e in bundle["supplemental"] if e["document_id"] == doc_id and contains in e["text"])


@pytest.mark.parametrize("cite", ["deployment", "web", "none"])
def test_a_one_sided_capability_fact_is_refused_whatever_it_cites(arup, cite):
    b = unrelated_both(arup)
    ids = {"deployment": [passage_id(b, "NVQ-PRD-001", "Deployment")],
           "web": [b["external"]["evidence"][0]["evidence_id"]], "none": []}[cite]
    found = issues_of(b, fact(SCIM_A, ids))
    assert [x["code"] for x in found] == ["one_sided_conflict_claim"] and "C2" in found[0]["message"]


def test_either_disputed_side_is_refused(arup):
    b = unrelated_both(arup)
    assert issues_of(b, fact(SCIM_B, []))


@pytest.mark.parametrize("item", [
    {"kind": "inference", "text": "SCIM provisioning may be limited to the Enterprise tier; verify.",
     "evidence_ids": [], "claim_type": None},
    {"kind": "recommendation", "text": "Ask whether SCIM provisioning is needed for all users.", "evidence_ids": [],
     "claim_type": None},
    {"kind": "fact", "text": "The vendor's documents disagree on which tiers include SCIM provisioning.",
     "evidence_ids": [], "claim_type": "vendor_product"},
])
def test_qualified_statements_and_questions_pass(arup, item):
    assert issues_of(unrelated_both(arup), item) == []


@pytest.mark.parametrize("text", [
    "Nivarque is offered as a hosted cloud service in EU and US regions.",   # an unrelated capability
    "The Records Retention add-on applies retention schedules.",
])
def test_valid_non_conflicting_claims_pass_even_when_the_briefing_mentions_the_disputed_subject(arup, text):
    b = unrelated_both(arup)
    draft = {"sections": {"meeting_recommendations": [fact(text, [passage_id(b, "NVQ-PRD-001", "Deployment")]),
                                                      {"kind": "recommendation", "text": "Ask about SCIM.",
                                                       "evidence_ids": [], "claim_type": None}]}, "disclosures": []}
    assert disclosures.one_sided_claims(b, draft, NOW.date()) == []


def test_no_conflict_in_the_evidence_no_claim_is_refused(arup):
    assert issues_of(arup, fact(SCIM_A, [])) == []


def test_a_conflict_disclosed_by_the_existing_rule_keeps_its_existing_check(arup, kb):
    b = with_passages(arup, chunk("NVQ-PRD-001", "Enterprise tier only"), chunk("NVQ-POL-002", "Where is customer"))
    orchestrator.add_conflict_sources(b, kb, NOW)
    from deal_prep.citations import validate_citations
    codes = {x["code"] for x in validate_citations(
        {"sections": {"meeting_recommendations": [fact(SCIM_A, [passage_id(b, "NVQ-PRD-001", "Enterprise tier")])]},
         "disclosures": []}, b)["issues"]}
    assert "unresolved_conflict_as_fact" in codes and "one_sided_conflict_claim" not in codes


def test_the_reserve_holds_the_statement_passages_of_set_aside_conflicts_outside_the_drafting_input(arup, kb):
    from deal_prep.evidence import evidence_index
    b = unrelated_both(arup)
    orchestrator.add_conflict_sources(b, kb, NOW)
    assert {e["document_id"] for e in b["conflict_reserve"]} == {"NVQ-PRD-001", "NVQ-POL-002"}
    assert not {e["evidence_id"] for e in b["conflict_reserve"]} & set(evidence_index(b))  # not model input


def scripted_draft(b, item):
    """A complete valid draft; the item goes where its kind is allowed (a fact or inference: opportunities)."""
    ok = [e["evidence_id"] for e in b["internal"]["company_profile"]["evidence"]
          if e["metadata"]["approval_status"] == "approved" and not e["metadata"].get("conflict_group")][0]
    record = next(e["evidence_id"] for e in b["internal"]["relationship_history"]["evidence"]
                  if e["metadata"]["approval_status"] == "approved" and not e["metadata"].get("conflict_group"))
    web = b["external"]["evidence"][0]["evidence_id"]
    return {"sections": {
        "company_overview": [{"kind": "fact", "text": "Arup is an engineering firm.", "evidence_ids": [ok],
                              "claim_type": "real_world_fact"}],
        "recent_developments": [{"kind": "fact", "text": "Arup won a design contract.", "evidence_ids": [web],
                                 "claim_type": "real_world_fact"}],
        "our_relationship": [{"kind": "fact", "text": "Synthetic record: negotiation in progress.",
                              "evidence_ids": [record], "claim_type": "relationship"}],
        "opportunities": [item] if item["kind"] != "recommendation"
        else [{"kind": "inference", "text": "Drawing control may matter.", "evidence_ids": [web]}],
        "competitive_positioning": [rec("Compare total cost.")],
        "meeting_recommendations": [item] if item["kind"] == "recommendation" else [rec("Confirm the user count.")]},
        "disclosures": [{"id": d["id"], "text": d["text"]} for d in required_disclosures(b)]}


def test_the_retry_corrects_a_one_sided_claim_and_the_final_briefing_discloses_both_sides_quoted(arup, kb):
    b = unrelated_both(arup)
    orchestrator.add_conflict_sources(b, kb, NOW)
    bad = scripted_draft(b, fact(SCIM_A, [passage_id(b, "NVQ-PRD-001", "Deployment")]))
    good = scripted_draft(b, {"kind": "inference", "text": "SCIM tiers may differ between the vendor's documents; "
                                                           "verify before promising it.",
                              "evidence_ids": [], "claim_type": None})
    outputs = [bad, good]
    out = draft_briefing(b, lambda messages: json.dumps(outputs.pop(0)))
    assert out["status"] == "ok" and out["retried"] and not outputs
    d = next(x for x in out["disclosures"] if x["id"] == "conflict:C2")
    assert SCIM_A in d["text"] and SCIM_B in d["text"]          # both statements, quoted from their passages
    assert {i.split("#")[0] for i in d["evidence_ids"]} == {"NVQ-PRD-001", "NVQ-POL-002"}
    from deal_prep.evidence import evidence_index
    assert set(d["evidence_ids"]) <= set(evidence_index(b))      # the cited passages are in the final evidence


def test_the_last_resort_turns_a_persistent_one_sided_claim_into_a_marked_inference_and_revalidates(arup, kb):
    from deal_prep.citations import validate_citations
    b = unrelated_both(arup)
    orchestrator.add_conflict_sources(b, kb, NOW)
    bad = scripted_draft(b, fact(SCIM_A, [passage_id(b, "NVQ-PRD-001", "Deployment")]))
    out = draft_briefing(b, lambda messages: json.dumps(bad))
    assert out["status"] == "ok"
    item = out["draft"]["sections"]["opportunities"][0]
    assert item["kind"] == "inference" and "disagree" in item["text"]
    assert out["conflict_guard"]["actions"][0]["action"] == "marked_for_verification"
    final = {"sections": out["draft"]["sections"], "disclosures": out["disclosures"]}  # as the reader receives it
    assert validate_citations(final, b)["valid"]                 # the corrected briefing validates again
    assert any(x["id"] == "conflict:C2" for x in out["disclosures"])


def test_a_briefing_that_never_mentions_the_subject_is_untouched(arup, kb):
    b = unrelated_both(arup)
    orchestrator.add_conflict_sources(b, kb, NOW)
    out = draft_briefing(b, lambda messages: json.dumps(scripted_draft(b, rec("Confirm the user count."))))
    assert out["status"] == "ok" and not out["retried"]
    assert not any(x["id"] == "conflict:C2" for x in out["disclosures"])
