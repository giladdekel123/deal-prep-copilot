"""Validation corrections (owner-approved 2026-11-14), offline only (template drafter and scripted model outputs):

1. A product demonstration must show the core document control the product evidence documents, capability by
   capability, separately from approval workflows; one keyword does not pass, a declared gap does not excuse it, and
   an incomplete plan is detected and repaired.
2. The discount-approval policy reaches every meeting about a customer with a current proposal, not only negotiations.
3. A general meeting with a new lead gets product descriptions and a fit-hypothesis topic.
(a) Eligibility limits keep the source's own wording: "only" only when the source says it.

Scenario checks use the development split (FICTIONAL TEST DATA); no company name is used by the rules themselves.
"""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from deal_prep import briefing, business, contract, selection

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_harness as h  # noqa: E402


def _item(kind, text, ids):
    return {"kind": kind, "text": text, "evidence_ids": ids, "claim_type": None}


DOC = {"id": "demo:document_control", "groups": [["PRD#0"]], "require_all": True, "no_gap": True,
       "labels": [label for label, _, _ in contract.DOCUMENT_CONTROL],
       "markers": [said for _, _, said in contract.DOCUMENT_CONTROL]}


# --- 1. core document control: every capability, separately from approval workflows -------------------------

def test_one_document_control_keyword_or_approval_workflows_alone_do_not_pass():
    for text in ("Show configurable approval workflows on the Business tier.",
                 "Show full-text search across matter files.",
                 "Show approval workflows plus version control."):
        cov = contract.coverage({"sections": {"meeting_recommendations": [_item("recommendation", text, ["PRD#0"])]},
                                 "disclosures": []}, [DOC])
        assert cov["topics"]["demo:document_control"] == "cited_only", text
        assert cov["missing_capabilities"]["demo:document_control"] and "demo:document_control" in contract.unmet(cov)


def test_every_capability_stated_across_the_citing_items_passes():
    draft = {"sections": {"meeting_recommendations": [
        _item("recommendation", "Show version control and check-in/check-out on a consent form.", ["PRD#0"]),
        _item("recommendation", "Show metadata tagging and full-text search across records.", ["PRD#0", "X#1"])]},
        "disclosures": []}
    cov = contract.coverage(draft, [DOC])
    assert cov["topics"]["demo:document_control"] == "communicated" and cov["missing_capabilities"] == {}


def test_capabilities_stated_without_citing_the_product_evidence_do_not_count():
    draft = {"sections": {"meeting_recommendations": [
        _item("recommendation", "Show version control, check-in/check-out, metadata and search.", ["OTHER#1"])]},
        "disclosures": []}
    assert contract.coverage(draft, [DOC])["topics"]["demo:document_control"] == "missing"


def test_a_declared_gap_does_not_excuse_documented_core_capabilities():
    draft = {"sections": {"meeting_recommendations": [_item("recommendation", "Show approval workflows.", ["PRD#0"])]},
             "disclosures": [{"id": "topic_gap:demo:document_control", "text": "Covered elsewhere."}]}
    assert contract.coverage(draft, [DOC])["topics"]["demo:document_control"] == "cited_only"


def test_research_and_check_in_with_the_customer_are_not_capabilities():
    text = "Research how they work and check in with the customer about metadata and versions."
    cov = contract.coverage({"sections": {"meeting_recommendations": [_item("recommendation", text, ["PRD#0"])]},
                             "disclosures": []}, [DOC])
    assert set(cov["missing_capabilities"]["demo:document_control"]) == {"check-in and check-out", "search"}


@pytest.fixture(scope="module")
def dev():
    return h.compile_split("dev")


class Capture:
    def __init__(self):
        from deal_prep.demo import TemplateDrafter
        self.inner, self.messages = TemplateDrafter(), []

    def __call__(self, messages):
        self.messages.append(messages)
        return self.inner(messages)


@pytest.fixture(scope="module")
def runs(dev):
    by = {sc["id"]: sc for c in dev for sc in c["scenarios"]}
    out = {}
    for sid in ("DEV-M2", "DEV-L2", "DEV-T1", "DEV-P1", "DEV-C2", "DEV-E2", "DEV-E1", "DEV-P2"):
        cap = Capture()
        rec = h.run_scenario(by[sid], dev, h.RUNS / "pytest" / "validation_corrections" / sid, "news_fixture",
                             generate=cap)
        out[sid] = (rec, json.loads(cap.messages[0][1]["content"]))
    return out


def topic(payload, tid):
    return next((t for t in payload["meeting_contract"]["essential_topics"] if t["id"] == tid), None)


@pytest.mark.parametrize("sid", ["DEV-M2", "DEV-L2"])
def test_demo_contract_requires_document_control_separately_from_approval_workflows(runs, sid):
    rec, payload = runs[sid]
    doc, wf = topic(payload, "demo:document_control"), topic(payload, "demo:approval_workflows")
    assert doc and wf and doc["section"] == wf["section"] == "meeting_recommendations"
    for label in ("version control", "check-in and check-out", "metadata", "search"):
        assert label in doc["requirement"], label
    assert "demo:workflows" not in rec["coverage"]["topics"]  # the old combined area is gone
    # The offline template ignores the contract: the measure reports the gap with each missing capability named.
    assert rec["coverage"]["topics"]["demo:document_control"] == "missing"


# --- the repair (production knowledge base, scripted model) --------------------------------------------------

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    from deal_prep.kb_index import build_kb_index
    d = tmp_path_factory.mktemp("validation_kb")
    build_kb_index(chroma_dir=d)
    return d


@pytest.fixture()
def demo_bundle(kb):
    from deal_prep.demo import OfflineNewsClient
    from deal_prep.orchestrator import gather_research
    from deal_prep.web_research import Budget, SearchConfig
    return gather_research("Arup", news_client=OfflineNewsClient(), budget=Budget(SearchConfig()), domain="arup.com",
                           purpose="product_demo", chroma_dir=kb, now=NOW)


class Scripted:
    def __init__(self, *outputs):
        self.outputs, self.seen = list(outputs), []

    def __call__(self, messages):
        self.seen.append(messages)
        out = self.outputs.pop(0)
        return out if isinstance(out, str) else json.dumps(out)


def test_an_incomplete_demo_plan_is_detected_and_repaired(demo_bundle):
    from deal_prep.demo import TemplateDrafter
    messages = briefing.build_messages(demo_bundle)
    doc = topic(json.loads(messages[1]["content"]), "demo:document_control")
    assert doc, "the product evidence documents core document control"
    ids = doc["evidence_ids"]
    first = json.loads(TemplateDrafter()(messages))
    first["sections"]["meeting_recommendations"].append(_item(
        "recommendation", "Show configurable approval workflows and full-text search.", ids))
    second = copy.deepcopy(first)
    second["sections"]["meeting_recommendations"][-1]["text"] = (
        "Show version control, check-in and check-out, metadata tagging and full-text search, then approval "
        "workflows.")
    model = Scripted(first, second)
    out = briefing.draft_briefing(demo_bundle, model, repair_coverage=True)
    assert len(model.seen) == 2 and out["coverage"]["repaired"] is True
    note = model.seen[1][-1]["content"]
    assert "Not yet stated: version control, check-in and check-out, metadata" in note
    assert "topic_gap disclosure does not apply" in note
    assert out["coverage"]["topics"]["demo:document_control"] == "communicated"


# --- 2. the approval policy follows the customer's commercial context ----------------------------------------

def test_context_documents_rule():
    proposal = [{"metadata": {"doc_type": "proposal"}}]
    other = [{"metadata": {"doc_type": "correspondence"}}]
    for purpose in ("follow_up", "general", "product_demo", "introduction"):
        assert ("commercial_context", selection.COMMERCIAL_CONTEXT) in \
            selection.context_documents(purpose, proposal, []), purpose
    assert selection.context_documents("negotiation", proposal, []) == []  # negotiation already brings it
    assert selection.context_documents("follow_up", other, []) == []  # no proposal, no policy
    assert selection.context_documents("general", [], []) == [("general", selection.NEW_LEAD_GENERAL)]
    assert selection.context_documents("general", other, []) == []  # not a new lead
    assert selection.context_documents("general", [], [{"evidence_id": "HIST-MTG-1#0"}]) == []


@pytest.mark.parametrize("sid", ["DEV-T1", "DEV-P1", "DEV-C2", "DEV-L2"])
def test_meetings_about_a_live_proposal_get_the_approval_policy_without_a_recorded_approval(runs, sid):
    rec, payload = runs[sid]
    assert "NVQ-POL-001#0" in rec["drafting_input"], sid
    a = rec["business_analysis"]
    assert a["approval_policy"]["status"] == "parsed"
    pos = [p for p in a["price_positions"] if p["status"] == "calculated"]
    assert pos and all("does not record that it was approved" in p["approval"]["text"] for p in pos)
    req = topic(payload, pos[0]["id"])["requirement"]
    assert "negotiation" not in req and "concession the customer has not asked for" in req
    assert topic(payload, "approval_policy") is None  # the negotiation topic is not imposed on other meetings


def test_negotiation_selection_is_unchanged(runs):
    rec, payload = runs["DEV-P2"]
    why = (rec.get("selection") or {}).get("evidence") or {}
    assert why, "the record carries the selection report"
    assert "NVQ-POL-001#0" in rec["drafting_input"] and topic(payload, "approval_policy")
    assert why["NVQ-POL-001#0"].startswith("purpose_document:negotiation:")
    assert not any(str(v).startswith("purpose_document:commercial_context:") for v in why.values())


def test_follow_up_policy_is_selected_for_the_commercial_context(runs):
    why = (runs["DEV-T1"][0].get("selection") or {}).get("evidence") or {}
    assert why["NVQ-POL-001#0"] == "purpose_document:commercial_context:policy"


# --- 3. a general meeting with a new lead -------------------------------------------------------------------

def test_a_general_meeting_with_a_new_lead_gets_product_descriptions_and_fit_hypotheses(runs):
    rec, payload = runs["DEV-E2"]
    assert any(i.startswith("NVQ-PRD-001#") for i in rec["drafting_input"])
    fit = topic(payload, "fit_hypotheses")
    assert fit and fit["section"] == "opportunities" and "hypothesis to verify" in fit["requirement"]
    assert contract.NEW_LEAD_GENERAL_BRIEF in payload["meeting_contract"]["purpose_brief"]
    assert "NVQ-POL-001#0" not in rec["drafting_input"]  # no proposal, no discount policy


def test_a_general_meeting_with_an_existing_customer_gets_no_new_lead_hypotheses(runs):
    rec, payload = runs["DEV-C2"]
    assert topic(payload, "fit_hypotheses") is None
    assert contract.NEW_LEAD_GENERAL_BRIEF not in payload["meeting_contract"]["purpose_brief"]


def test_an_introduction_is_unchanged(runs):
    rec, payload = runs["DEV-E1"]
    assert topic(payload, "fit_hypotheses") and contract.NEW_LEAD_GENERAL_BRIEF not in \
        payload["meeting_contract"]["purpose_brief"]


# --- (a) eligibility wording ---------------------------------------------------------------------------------

@pytest.mark.parametrize("sentence,only", [
    ("The Business tier adds configurable approval workflows.", False),
    ("SCIM user provisioning is available on the Enterprise tier only.", True),
    ("A single-tenant private-cloud deployment is available for Engineering Vault customers.", False),
    ("Customer-supplied keys are available only to Engineering Vault customers.", True),
    ("Engineering Vault customers can supply their own encryption keys.", False),
])
def test_eligibility_limit_keeps_the_sources_own_wording(sentence, only):
    for pattern, kind in business._ELIGIBILITY:
        m = pattern.search(sentence)
        if m:
            limit = business._limit_wording(m.group(0), m["q"], kind)
            assert ("only" in limit.replace("do not say 'only'", "")) is only, limit
            return
    raise AssertionError(f"no eligibility pattern matched: {sentence}")


def test_demo_eligibility_topics_use_the_source_wording(runs):
    rec, payload = runs["DEV-M2"]
    elig = rec["business_analysis"]["eligibility"]
    adds = [e for e in elig if "tier adds" in e["capability"]]
    assert all("do not say 'only'" in e["limit"] for e in adds)
    for e in elig:
        assert e["limit"] in topic(payload, e["id"])["requirement"]
