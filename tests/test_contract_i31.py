"""Phase 4.5 I3.1 (early CP-3): meeting-purpose drafting contract and final-output coverage.

Offline only: the template drafter and simulated model outputs. The scenario tests use the six audited development
scenarios (FICTIONAL TEST DATA) to check that the topics follow the meeting purpose and the selected evidence.
"""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from deal_prep import briefing, contract

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_harness as h  # noqa: E402

SIX = ("DEV-P2", "DEV-T1", "DEV-C1", "DEV-L1", "DEV-E1", "DEV-M2")


# --- pure rules ---------------------------------------------------------------------------------------

def test_figures_ignore_dates_years_and_document_ids():
    text = ("Subject: (NVQ-PRP-BXP-001). Date: 29 October 2026. Asked for 60 additional users and a 36-month "
            "term, due 2026-11-16, decided in 2022, price 49.")
    assert contract.figures(text) == ["36", "49", "60"]


def _item(kind, text, ids, claim=None):
    return {"kind": kind, "text": text, "evidence_ids": ids, "claim_type": claim}


TOPICS = [{"id": "price", "groups": [["P#2"]], "markers": [r"(?<![\d.])52(?![\d])"]},
          {"id": "both", "groups": [["A#1"], ["B#1"]], "markers": [r"(?<![\d.])4(?![\d])"]},
          {"id": "gap", "groups": [["G#0"]], "markers": [r"\bretention"]}]


def test_coverage_needs_the_evidence_and_its_content_not_only_a_citation():
    draft = {"sections": {"opportunities": [_item("inference", "Check the list price.", ["P#2"])],
                          "company_overview": [_item("inference", "Sources give 4 and 5.", ["A#1"])]},
             "disclosures": [{"id": "topic_gap:gap", "text": "No retention evidence for this customer."}]}
    cov = contract.coverage(draft, TOPICS)
    assert cov["topics"] == {"price": "cited_only", "both": "missing", "gap": "gap_declared"}
    draft["sections"]["opportunities"][0]["text"] = "The current list price is USD 52 per user per month."
    draft["sections"]["company_overview"][0]["evidence_ids"] = ["A#1", "B#1"]
    cov = contract.coverage(draft, TOPICS)
    assert cov["topics"]["price"] == cov["topics"]["both"] == "communicated" and contract.unmet(cov) == []


# --- topics in the six audited scenarios ----------------------------------------------------------------

class Capture:
    def __init__(self):
        from deal_prep.demo import TemplateDrafter
        self.inner, self.messages = TemplateDrafter(), []

    def __call__(self, messages):
        self.messages.append(messages)
        return self.inner(messages)


@pytest.fixture(scope="module")
def runs():
    dev = h.compile_split("dev")
    by = {sc["id"]: sc for c in dev for sc in c["scenarios"]}
    out = {}
    for sid in SIX:
        cap = Capture()
        rec = h.run_scenario(by[sid], dev, h.RUNS / "pytest" / "i31" / sid, "news_fixture", generate=cap)
        out[sid] = (rec, json.loads(cap.messages[0][1]["content"]), cap.messages[0][0]["content"])
    return out


LATER = {"undated", "chronology",  # I4
         "price_position", "requested_addition", "requested_term", "urgent", "status_check", "date_check",
         "eligibility",  # I5
         "company", "discovery"}  # I7 (tests/test_company_context_i7.py)


def kinds(payload):  # topics added by I4 and I5 are tested in their own files; I3.1 topics are checked here
    return sorted({t["id"].split(":")[0] for t in payload["meeting_contract"]["essential_topics"]} - LATER)


def test_topics_follow_the_meeting_purpose(runs):
    assert kinds(runs["DEV-M2"][1]) == ["contested", "demo"]
    assert len([t for t in runs["DEV-M2"][1]["meeting_contract"]["essential_topics"]
                if t["id"].startswith("demo:")]) == len(contract.DEMO_AREAS)
    for sid in ("DEV-P2", "DEV-C1"):
        assert {"approval_policy", "customer_request", "list_price", "open_task", "proposal_terms"} <= \
            set(kinds(runs[sid][1])), sid
    for sid in ("DEV-T1", "DEV-L1"):
        assert {"customer_request", "list_price", "open_task"} <= set(kinds(runs[sid][1])), sid
        assert "approval_policy" not in kinds(runs[sid][1])
    assert kinds(runs["DEV-E1"][1]) == ["contested", "fit_hypotheses"]


def test_completed_tasks_are_not_essential_open_items(runs):
    rec, payload, _ = runs["DEV-T1"]  # one task open, one completed
    assert len([t for t in payload["meeting_contract"]["essential_topics"] if t["id"].startswith("open_task:")]) == 1


@pytest.mark.parametrize("sid", SIX)
def test_topics_cite_only_drafting_input_and_send_no_scoring_markers(runs, sid):
    rec, payload, system = runs[sid]
    topics = payload["meeting_contract"]["essential_topics"]
    assert topics and all(set(t["evidence_ids"]) <= set(rec["drafting_input"]) for t in topics)
    assert all(set(t) == {"id", "section", "requirement", "evidence_ids"} for t in topics)
    assert "Meeting contract:" in system and payload["meeting_contract"]["purpose_brief"]
    assert set(rec["coverage"]["topics"]) == {t["id"] for t in topics}


def test_the_contract_shows_where_the_offline_template_falls_short(runs):
    # The template ignores the contract: its uncovered topics are exactly the audit's drafting gaps.
    cov = runs["DEV-M2"][0]["coverage"]["topics"]
    assert all(s == "missing" for t, s in cov.items() if t.startswith("demo:"))
    assert runs["DEV-E1"][0]["coverage"]["topics"]["fit_hypotheses"] == "missing"


def test_with_the_contract_off_the_prompt_is_exactly_the_i3_prompt(runs, monkeypatch):
    dev = h.compile_split("dev")
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == "DEV-C1")
    monkeypatch.setattr(briefing, "CONTRACT_IN_MODEL_INPUT", False)
    cap = Capture()
    rec = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "i31" / "off", "news_fixture", generate=cap)
    system, user = cap.messages[0][0]["content"], json.loads(cap.messages[0][1]["content"])
    assert system == briefing.SYSTEM_RULES and "meeting_contract" not in user
    assert rec["coverage"]["contract_in_model_input"] is False and rec["coverage"]["total"] > 0  # still measured


# --- the coverage repair (production knowledge base, simulated model) -----------------------------------

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    from deal_prep.kb_index import build_kb_index
    d = tmp_path_factory.mktemp("i31_kb")
    build_kb_index(chroma_dir=d)
    return d


@pytest.fixture()
def arup(kb):
    from deal_prep.demo import OfflineNewsClient
    from deal_prep.orchestrator import gather_research
    from deal_prep.web_research import Budget, SearchConfig
    return gather_research("Arup", news_client=OfflineNewsClient(), budget=Budget(SearchConfig()), domain="arup.com",
                           purpose="negotiation", chroma_dir=kb, now=NOW)


class Scripted:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), 0

    def __call__(self, messages):
        self.calls += 1
        out = self.outputs.pop(0)
        return out if isinstance(out, str) else json.dumps(out)


def template_draft(bundle):
    from deal_prep.demo import TemplateDrafter
    return json.loads(TemplateDrafter()(briefing.build_messages(bundle)))


def with_policy(draft):
    d = copy.deepcopy(draft)
    d["sections"]["meeting_recommendations"].append(_item(
        "recommendation", "Account executives may approve up to 15 percent; above 15 percent needs the regional "
                          "sales director, above 25 percent the CFO.", ["NVQ-POL-001#0"]))
    return d


def test_repair_is_used_only_when_valid_and_more_complete(arup):
    first = template_draft(arup)
    assert "approval_policy" in contract.unmet(contract.coverage(first, contract.essential_topics(arup)))
    model = Scripted(first, with_policy(first))
    out = briefing.draft_briefing(arup, model, repair_coverage=True)
    assert out["status"] == "ok" and model.calls == 2 and out["coverage"]["repaired"] is True
    assert out["coverage"]["topics"]["approval_policy"] == "communicated"
    assert out["coverage"]["counts"]["communicated"] > out["coverage"]["first_draft"]["communicated"]


@pytest.mark.parametrize("second", ["not json", "INVALID_CITATION", "MODEL_ERROR"])
def test_a_failed_repair_keeps_the_valid_first_draft(arup, second):
    first = template_draft(arup)
    if second == "INVALID_CITATION":
        bad = with_policy(first)
        bad["sections"]["meeting_recommendations"][-1]["evidence_ids"] = ["NVQ-NOPE-999#0"]
        second = bad

    def model(messages, outputs=[first, second]):  # noqa: B006
        out = outputs.pop(0)
        if out == "MODEL_ERROR":
            raise RuntimeError("simulated model failure")
        return out if isinstance(out, str) else json.dumps(out)
    out = briefing.draft_briefing(arup, model, repair_coverage=True)
    assert out["status"] == "ok" and out["coverage"]["repaired"] is False
    assert out["draft"] == briefing._parse(json.dumps(first)).model_dump()


def test_no_repair_unless_enabled_and_the_contract_is_in_the_input(arup, monkeypatch):
    first = template_draft(arup)
    model = Scripted(first)
    assert briefing.draft_briefing(arup, model)["status"] == "ok" and model.calls == 1
    monkeypatch.setattr(briefing, "CONTRACT_IN_MODEL_INPUT", False)
    model = Scripted(first)
    assert briefing.draft_briefing(arup, model, repair_coverage=True)["status"] == "ok" and model.calls == 1


def test_a_declared_topic_gap_is_shown_with_the_briefing(arup):
    d = template_draft(arup)
    d["disclosures"].append({"id": "topic_gap:approval_policy", "text": "The approval thresholds were not retrieved."})
    out = briefing.draft_briefing(arup, Scripted(d))
    assert out["coverage"]["topics"]["approval_policy"] == "gap_declared"
    assert {"id": "topic_gap:approval_policy", "kind": "topic_gap",
            "text": "The approval thresholds were not retrieved."} in out["disclosures"]
