"""Phase 4.5 I5: deterministic business analysis (offline; simulated evidence, the production knowledge base and the
six audited development scenarios, FICTIONAL TEST DATA). Includes the negative cases: missing prices, incompatible
units or currencies, conflicting prices, ambiguous or missing approval policies, unpriced products."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from deal_prep import briefing, business

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_harness as h  # noqa: E402

LIST = "List prices\nProduct: Acme Vault | Tier: Enterprise | Unit: per user per month | List price (USD): 52 | Minimum term: 24 months"
ADDON = "List prices\nProduct: Acme Archive Add-on | Tier: Add-on | Unit: per TB per month | List price (USD): 240 | Minimum term: 12 months"
PROPOSAL = ("Proposed pricing\nProduct: Acme Vault | Tier: Enterprise | Quantity: 180 | Unit: per user per month | "
            "Proposed price (USD): 49 | Valid until: 20 December 2026")
SENT = "Scope\nThis proposal was sent on 12 October 2026. No decision has been recorded."
POLICY = ("Discount approval policy Account executives may approve discounts of up to 15 percent from the list price. "
          "Discounts above 15 percent require written approval from the regional sales director. Discounts above 25 "
          "percent require approval from the CFO.")


def ev(eid, text, doc_type, customer=None, section="", approval="approved", effective_from="2026-10-01"):
    meta = {"doc_type": doc_type, "approval_status": approval, "section": section, "customer_org_id": customer or "",
            "conflict_group": "", "effective_from": effective_from, "scope": "company" if customer else "global"}
    return {"evidence_id": eid, "document_id": eid.split("#")[0], "text": text, "info_origin": "synthetic_record",
            "provenance_label": "SYNTHETIC ג€” not a real business fact ֲ· test", "metadata": meta}


def meeting(tasks, eid="HIST-T#0"):
    return {"evidence_id": eid, "document_id": eid.split("#")[0], "text": "Meeting record (2026-10-20): review.",
            "info_origin": "synthetic_record", "provenance_label": "SYNTHETIC ג€” test",
            "record": {"follow_up_tasks": tasks, "concerns": [], "decisions": [], "commitments": []},
            "metadata": {"doc_type": "meeting_record", "approval_status": "approved", "customer_org_id": "acme",
                         "conflict_group": ""}}


def bundle(vendor=(), customer=(), meetings=(), in_play=("Acme Vault",), purpose="negotiation"):
    return {"created_at": "2026-11-09T09:00:00+00:00", "purpose": purpose, "status": "complete", "gaps": [],
            "identity": {"name": "Acme Test", "org_id": "acme", "domain": "acme.example"},
            "internal": {"vendor_products_pricing": {"sections": [], "evidence": list(vendor)},
                         "relationship_history": {"sections": [], "evidence": list(customer)},
                         "meeting_history": {"sections": [], "evidence": list(meetings)}},
            "external": {"evidence": []}, "selection": {"products_in_play": list(in_play)}, "trace": []}


def standard(**over):
    vendor = over.pop("vendor", [ev("PRC#1", LIST, "price_list", section="List prices"),
                                 ev("POL#0", POLICY, "policy", section="Discount approval policy")])
    customer = over.pop("customer", [ev("PRP#1", SENT, "proposal", "acme", "Scope"),
                                     ev("PRP#2", PROPOSAL, "proposal", "acme", "Proposed pricing")])
    return business.analyse(bundle(vendor, customer, **over))


# --- price position and approval -------------------------------------------------------------------------

def test_discount_from_list_with_its_formula_inputs_and_evidence():
    p = standard()["price_positions"][0]
    assert p["status"] == "calculated" and p["discount_pct"] == 5.77 and p["discount_display"] == "5.8%"
    assert p["formula"] == "discount = (list price - proposed price) / list price = (52 - 49) / 52 = 5.77%"
    assert {i["evidence_id"] for i in p["inputs"]} == {"PRC#1", "PRP#2"} and "POL#0" in p["evidence_ids"]
    assert p["value"]["proposed_monthly"] == 8820 and p["value"]["difference_12_months"] == 6480
    assert p["offer_status"] == {"text": "No decision has been recorded.", "evidence_id": "PRP#1"}
    assert p["validity"] == {"valid_until": "2026-12-20", "days_left": 41, "evidence_id": "PRP#2"}
    assert p["caveats"][0]["text"] == "The proposed price is an offer, not an agreed price."


def test_approval_tier_and_the_price_below_which_more_approval_is_needed():
    p = standard()["price_positions"][0]
    ap = p["approval"]
    assert ap["status"] == "classified" and ap["required"] == "the authority of account executives"
    assert "does not record that it was approved" in ap["text"]
    assert [(f["display"], f["above_pct"]) for f in ap["price_floors"]] == [("USD 44.20", 15.0), ("USD 39", 25.0)]
    assert "below USD 44.20" in ap["text"] and "regional sales director" in ap["text"]


@pytest.mark.parametrize("discount, approver", [(0.0, "account executives"), (15.0, "account executives"),
                                                (15.01, "regional sales director"), (25.0, "regional sales director"),
                                                (25.01, "CFO")])
def test_approval_tier_boundaries_follow_the_policy_wording(discount, approver):
    policy = business.approval_policy([ev("POL#0", POLICY, "policy", section="Discount approval policy")])
    assert approver.casefold() in business._tier_for(discount, policy)["approver"].casefold()


@pytest.mark.parametrize("text, why", [
    ("Account executives may approve discounts of up to 15 percent from the list price. Discounts above 10 percent "
     "require written approval from the regional sales director.", "do not meet"),
    ("Discounts above 15 percent require written approval from the regional sales director.", "who may approve"),
    ("Account executives may approve discounts of up to 15 percent from the proposed price. Discounts above 15 "
     "percent require approval from the CFO.", "list price"),
    ("Account executives may approve discounts of up to 15 percent from the list price. Sales managers may approve "
     "discounts of up to 20 percent from the list price.", "different base approval limits"),
])
def test_an_ambiguous_policy_gives_no_approval_tier_only_a_reason_to_verify(text, why):
    a = standard(vendor=[ev("PRC#1", LIST, "price_list", section="List prices"), ev("POL#0", text, "policy")])
    assert a["approval_policy"]["status"] == "ambiguous" and why in a["approval_policy"]["reason"]
    p = a["price_positions"][0]
    assert p["status"] == "calculated" and p["approval"]["status"] == "ambiguous" and "Verify" in p["approval"]["text"]
    assert "price_floors" not in p["approval"]
    assert any(v["about"] == "approval_policy" for v in a["verification_needed"])


def test_no_policy_in_the_evidence_means_approval_is_unknown_not_assumed():
    a = standard(vendor=[ev("PRC#1", LIST, "price_list", section="List prices")])
    assert a["approval_policy"]["status"] == "not_in_evidence"
    assert a["price_positions"][0]["approval"]["status"] == "not_in_evidence"


@pytest.mark.parametrize("vendor, why", [
    ([], "No current list price"),  # missing price
    ([ev("PRC#1", LIST.replace("per user per month", "per site per month"), "price_list")], "units differ"),
    ([ev("PRC#1", LIST.replace("(USD)", "(EUR)"), "price_list")], "no exchange rate"),
    ([ev("PRC#1", LIST, "price_list"), ev("PRC#2", LIST.replace(": 52", ": 55"), "price_list")], "conflicting"),
    ([ev("PRC#1", LIST.replace("Tier: Enterprise", "Tier: Starter"), "price_list"),
      ev("PRC#2", LIST.replace("Tier: Enterprise", "Tier: Business"), "price_list")], "other tiers"),
])
def test_missing_or_incompatible_prices_are_never_compared(vendor, why):
    p = standard(vendor=vendor)["price_positions"][0]
    assert p["status"] == "not_calculable" and why in p["reason"] and "discount_pct" not in p


def test_a_proposal_sent_before_the_current_list_took_effect_is_flagged():
    a = standard(vendor=[ev("PRC#1", LIST, "price_list", section="List prices", effective_from="2026-11-01")])
    assert any("before the current list price took effect" in c["text"] for c in a["price_positions"][0]["caveats"])


# --- requested additions and terms --------------------------------------------------------------------------

def request(text):
    return ev("COR#2", text, "correspondence", "acme")


def test_the_list_price_cost_of_a_requested_addition_with_its_minimum_term():
    a = standard(vendor=[ev("PRC#1", LIST, "price_list"), ev("PRC#3", ADDON, "price_list")],
                 customer=[ev("PRP#2", PROPOSAL, "proposal", "acme"),
                           request("The director asked for the Acme Archive Add-on for 8 TB of archives.")])
    r = a["requested_additions"][0]
    assert r["status"] == "calculated" and r["monthly_at_list"] == 1920 and r["minimum_term_at_list"] == 23040
    assert r["basis"] == "list price; not a quote or an agreed price" and r["formula"] == "8 x 240 = 1920 per month at list"


def test_additional_users_are_priced_at_list_and_counted_with_the_proposal():
    a = standard(customer=[ev("PRP#2", PROPOSAL, "proposal", "acme"),
                           request("The director asked for a revised quote covering 60 additional users.")])
    r = a["requested_additions"][0]
    assert r["monthly_at_list"] == 3120 and r["quantity_after_addition"] == 240
    assert "no price for the additional users has been quoted" in r["display"]


@pytest.mark.parametrize("text, why", [
    ("The director asked for the Acme Archive Add-on for 8 GB of archives.", "units differ"),
    ("The director asked for 5 TB of storage.", "names no product"),
    ("The director asked for the Acme Vault for 8 TB of drawings.", "units differ"),
])
def test_a_request_with_an_incompatible_unit_or_no_priced_product_gets_no_cost(text, why):
    a = standard(vendor=[ev("PRC#1", LIST, "price_list"), ev("PRC#3", ADDON, "price_list")],
                 customer=[ev("PRP#2", PROPOSAL, "proposal", "acme"), request(text)])
    r = a["requested_additions"][0]
    assert r["status"] == "not_calculable" and why in r["reason"]


def test_a_requested_term_is_checked_against_the_minimum_but_never_priced():
    a = standard(customer=[ev("PRP#2", PROPOSAL, "proposal", "acme"),
                           request("The manager asked whether the price would fall for a 36-month term.")])
    r = a["requested_additions"][0]
    assert r["status"] == "not_calculable" and "No rule in the evidence links a longer contract term" in r["reason"]
    assert r["minimum_term_check"] == "A 36-month term meets the 24-month minimum term."


# --- deadlines, status checks, eligibility ---------------------------------------------------------------------

def test_deadlines_count_days_from_the_briefing_date_and_skip_completed_tasks():
    tasks = [{"description": "Send the import template", "status": "Open", "due_date": "2026-11-10"},
             {"description": "Send the sizing questionnaire", "status": "In Progress", "due_date": "2026-11-05"},
             {"description": "Share the checklist", "status": "Completed", "due_date": "2026-11-01"}]
    d = {x["what"]: x for x in standard(meetings=[meeting(tasks)])["deadlines"]}
    assert d["Send the import template"]["urgency"] == "due tomorrow" and d["Send the import template"]["days_left"] == 1
    assert d["Send the sizing questionnaire"]["urgency"] == "overdue" and d["Send the sizing questionnaire"]["days_left"] == -4
    assert "Share the checklist" not in d


def correspondence(status):
    return [ev("COR#3", "Nivarque replied that the revised quote will be sent by 18 November 2026.", "correspondence",
               "acme"), ev("COR#4", f"Status: {status}", "correspondence", "acme")]


def test_a_completed_task_with_the_request_still_open_in_correspondence_is_a_status_disagreement():
    tasks = [{"description": "Send the revised quote including retention", "status": "Completed",
              "due_date": "2026-11-18"}]
    a = standard(customer=correspondence("retention options requested."), meetings=[meeting(tasks)])
    (s,) = a["status_checks"]
    assert s["kind"] == "status_disagreement" and "Verify whether the customer has received it" in s["text"]
    assert s["task_evidence_id"] == "HIST-T#0" and s["correspondence_evidence_ids"] == ["COR#3", "COR#4"]


@pytest.mark.parametrize("task", [
    {"description": "Send the revised quote including retention", "status": "Open", "due_date": "2026-11-18"},
    {"description": "Share the customs archive migration checklist", "status": "Completed", "due_date": "2026-10-31"},
])
def test_consistent_or_unrelated_records_are_not_flagged(task):
    a = standard(customer=correspondence("revised quote requested; not yet sent."), meetings=[meeting([task])])
    assert a["status_checks"] == []


def test_different_committed_dates_are_flagged():
    tasks = [{"description": "Send the revised quote including retention", "status": "Open", "due_date": "2026-11-20"}]
    a = standard(customer=correspondence("revised quote requested."), meetings=[meeting(tasks)])
    assert [s["kind"] for s in a["status_checks"]] == ["date_disagreement"]


def test_capabilities_limited_to_a_product_not_in_play_are_listed_with_their_triggers():
    faq = ev("FAQ#1", "Q: How is data encrypted? A: Documents are encrypted at rest with AES-256. Acme Vault "
                      "customers can supply their own encryption keys.", "policy")
    a = business.analyse(bundle([faq], [], in_play=()))
    (e,) = a["eligibility"]
    assert e["available_to"] == "Acme Vault customers" and e["triggers"] == ["key", "supply"]
    assert business.analyse(bundle([faq], [], in_play=("Acme Vault",)))["eligibility"] == []  # held: not needed


# --- figure tracing -----------------------------------------------------------------------------------------

def test_figures_that_appear_nowhere_or_calculations_stated_as_facts_are_found():
    b = bundle([ev("PRC#1", LIST, "price_list"), ev("POL#0", POLICY, "policy")],
               [ev("PRP#2", PROPOSAL, "proposal", "acme")])
    a = business.analyse(b)

    def draft(kind, text, ids):
        return {"sections": {"our_relationship": [{"kind": kind, "text": text, "evidence_ids": ids,
                                                   "claim_type": "relationship" if kind == "fact" else None}]}}
    ok = business.figure_check(draft("inference", "The proposal is 5.8% below the USD 52 list price.",
                                     ["PRP#2", "PRC#1"]), b, a)
    assert ok["untraced"] == [] and ok["calculated_in_fact"] == [] and ok["mismatched"] == []  # C1: + mismatched
    invented = business.figure_check(draft("inference", "A 17% discount would be acceptable.", ["PRP#2"]), b, a)
    assert [x["figure"] for x in invented["untraced"]] == ["17"]
    as_fact = business.figure_check(draft("fact", "The proposal is 5.8% below list.", ["PRP#2", "PRC#1"]), b, a)
    assert [x["figure"] for x in as_fact["calculated_in_fact"]] == ["5.8"]


# --- the six audited development scenarios (offline) -----------------------------------------------------------

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
    for sid in ("DEV-P2", "DEV-T1", "DEV-C1", "DEV-L1", "DEV-M2"):
        cap = Capture()
        rec = h.run_scenario(by[sid], dev, h.RUNS / "pytest" / "i5" / sid, "news_fixture", generate=cap)
        out[sid] = (rec, json.loads(cap.messages[0][1]["content"]), cap.messages[0][0]["content"])
    return out


def test_scenario_price_positions_and_approval(runs):
    got = {sid: [(p["discount_pct"], p["approval"]["status"]) for p in r[0]["business_analysis"]["price_positions"]]
           for sid, r in runs.items() if sid != "DEV-M2"}
    # Validation correction (owner-approved 2026-11-14): the discount policy now reaches every meeting about a customer
    # with a current proposal, so the follow-ups T1 and L1 classify their discount too (it was "not_in_evidence").
    assert got == {"DEV-P2": [(5.77, "classified")], "DEV-C1": [(9.62, "classified")],
                   "DEV-T1": [(8.82, "classified")], "DEV-L1": [(5.88, "classified")]}
    assert runs["DEV-M2"][0]["business_analysis"]["price_positions"] == []  # a new lead: nothing to compare


def test_scenario_requests_deadlines_status_and_eligibility(runs):
    a = {sid: r[0]["business_analysis"] for sid, r in runs.items()}
    costs = {sid: [x.get("monthly_at_list") for x in a[sid]["requested_additions"]] for sid in a}
    assert costs == {"DEV-P2": [3120], "DEV-T1": [1920], "DEV-C1": [None], "DEV-L1": [720], "DEV-M2": []}
    assert a["DEV-C1"]["requested_additions"][0]["status"] == "not_calculable"  # 36-month term: no rule
    assert [d["urgency"] for d in a["DEV-C1"]["deadlines"]][0] == "due tomorrow"
    assert [s["kind"] for s in a["DEV-L1"]["status_checks"]] == ["status_disagreement"]
    assert all(a[sid]["status_checks"] == [] for sid in ("DEV-P2", "DEV-T1", "DEV-C1"))
    assert {e["marker"] for e in a["DEV-M2"]["eligibility"]} == {"Business", "Engineering Vault"}


def test_the_drafter_receives_the_analysis_and_the_i5_rules(runs):
    rec, payload, system = runs["DEV-P2"]
    assert payload["business_analysis"]["price_positions"][0]["discount_display"] == "5.8%"
    assert "Business analysis:" in system
    ids = {t["id"] for t in payload["meeting_contract"]["essential_topics"]}
    assert "price_position:NVQ-PRP-BXP-001#2" in ids and any(i.startswith("urgent:") for i in ids)


def test_with_i5_off_the_prompt_is_exactly_the_i4_prompt(monkeypatch):
    monkeypatch.setattr(business, "ENABLED", False)
    dev = h.compile_split("dev")
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == "DEV-C1")
    cap = Capture()
    rec = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "i5" / "off", "news_fixture", generate=cap)
    system, user = cap.messages[0][0]["content"], json.loads(cap.messages[0][1]["content"])
    assert system == briefing.SYSTEM_RULES + briefing.CONTRACT_RULES + briefing.I4_RULES
    assert "business_analysis" not in user
    assert not any(t["id"].startswith(("price_position", "urgent", "eligibility"))
                   for t in user["meeting_contract"]["essential_topics"])
    assert rec["coverage"]["i5_measure"]["total"] > 0  # still measured, for a comparable A/B


# --- production knowledge base (no benchmark data) ----------------------------------------------------------

@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    from deal_prep.kb_index import build_kb_index
    d = tmp_path_factory.mktemp("i5_kb")
    build_kb_index(chroma_dir=d)
    return d


def test_production_negotiation_matches_its_own_recorded_discount_and_leaves_unpriced_items_unpriced(kb):
    from deal_prep.demo import OfflineNewsClient
    from deal_prep.orchestrator import gather_research
    from deal_prep.web_research import Budget, SearchConfig
    b = gather_research("Arup", news_client=OfflineNewsClient(), budget=Budget(SearchConfig()), domain="arup.com",
                        purpose="negotiation", chroma_dir=kb, now=datetime(2026, 11, 6, 12, tzinfo=timezone.utc))
    a = business.analyse(b)
    by_product = {p["product"]: p for p in a["price_positions"]}
    vault = by_product["Nivarque Engineering Vault"]
    assert vault["discount_pct"] == 11.54 and vault["approval"]["required"] == "the authority of account executives"
    # The proposal's own text records "a discount of about 11.5 percent from the 2026 list price of 52".
    services = by_product["Implementation Services"]
    assert services["status"] == "not_calculable" and "No current list price" in services["reason"]
