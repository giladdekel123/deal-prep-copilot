"""Phase 4.5 I3: customer correspondence and purpose-aware selection (FICTIONAL TEST DATA for the scenario tests).

Requirements come from the CP-2 quality audit (eval/benchmark_v1/CP2_QUALITY_AUDIT.md): the error register items
fixed in I3 (E2-E5, E7, E10, E12, E14, E15) and its suggested acceptance additions. The scenario tests run the six
audited development scenarios offline through the unchanged benchmark harness and check the DRAFTING INPUT, i.e.
selection, so a later miss can be attributed to the drafter. The scorer is not involved.
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from deal_prep import selection as sel
from deal_prep.evidence_profile import is_data_page

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_harness as h  # noqa: E402

TODAY = date(2026, 11, 9)
SIX = {"DEV-P2": "negotiation", "DEV-T1": "follow_up", "DEV-C1": "negotiation", "DEV-L1": "follow_up",
       "DEV-E1": "introduction", "DEV-M2": "product_demo"}
REASONS = ("ranked_search:", "customer_record:", "price_row_in_play:", "current_price_row:", "price_list_notes",
           "purpose_document:", "product_in_play:", "public_source_excerpt:", "neutral_guidance:",
           "approved_meeting_record",
           "comparison_source", "conflict_source", "news:", "agent:")


# --- pure rules ---------------------------------------------------------------------------------------

def row(eid, product, tier, price="1"):
    return {"evidence_id": eid, "text": f"List prices\nProduct: {product} | Tier: {tier} | Unit: per user per month | "
                                        f"List price (USD): {price}", "metadata": {"doc_type": "price_list"}}


ROWS = [row("P#0", "Nivarque Core", "Starter"), row("P#1", "Nivarque Core", "Business"),
        row("P#2", "Nivarque Engineering Vault", "Enterprise"), row("P#3", "Records Retention Add-on", "Add-on")]


def test_rows_in_play_follow_the_customer_records_and_the_named_tier():
    text = "Nivarque proposes Nivarque Core (Business tier) for 250 users. Asked for the Records Retention Add-on."
    assert [r["evidence_id"] for r in sel.rows_in_play(text, ROWS)] == ["P#1", "P#3"]


def test_a_product_without_a_named_tier_brings_all_its_tiers_and_nothing_else():
    assert [r["evidence_id"] for r in sel.rows_in_play("We discussed Nivarque Core.", ROWS)] == ["P#0", "P#1"]
    assert sel.rows_in_play("No product was discussed.", ROWS) == []


def test_a_passage_is_about_the_first_product_it_names():
    products = ["Nivarque Core", "Nivarque Engineering Vault", "Records Retention Add-on"]
    assert sel.first_product("Nivarque Engineering Vault extends Nivarque Core Business.", products) == \
        "Nivarque Engineering Vault"
    assert sel.first_product("Nivarque supports SAML 2.0 on all tiers.", products) is None


@pytest.mark.parametrize("meta, expected", [
    ({"approval_status": "approved", "effective_from": "2026-10-01", "effective_to": ""}, True),
    ({"approval_status": "superseded", "effective_from": "2025-10-01", "effective_to": "2026-09-30",
      "superseded_by": "X"}, False),
    ({"approval_status": "approved", "effective_from": "2026-12-01", "effective_to": ""}, False),  # not yet
    ({"approval_status": "approved", "effective_from": "2026-01-01", "effective_to": "2026-10-31"}, False),  # ended
    ({"approval_status": "draft", "effective_from": "", "effective_to": ""}, False),
])
def test_in_force_needs_approval_and_the_briefing_date_inside_the_effective_period(meta, expected):
    assert sel.in_force(meta, TODAY) is expected


def test_agent_lookups_are_screened_by_the_same_rules_and_every_exclusion_is_recorded():
    bundle = {"selection": {"as_of": TODAY.isoformat(), "products_in_play": ["Nivarque Engineering Vault"],
                            "competition": {"relevant": False, "reason": "no competitor named"}, "excluded": []}}
    old = {**row("OLD#2", "Nivarque Engineering Vault", "Enterprise", "48"),
           "metadata": {"doc_type": "price_list", "scope": "global", "approval_status": "superseded",
                        "superseded_by": "NEW", "effective_from": "2025-10-01", "effective_to": "2026-09-30"}}
    new = {**row("NEW#2", "Nivarque Engineering Vault", "Enterprise", "52"),
           "metadata": {"doc_type": "price_list", "scope": "global", "approval_status": "approved",
                        "effective_from": "2026-10-01", "effective_to": ""}}
    other = {**row("NEW#0", "Nivarque Core", "Starter"), "metadata": new["metadata"]}
    card = {"evidence_id": "CMP#0", "text": "Competitor summary", "metadata": {"doc_type": "battlecard"}}
    record = {"evidence_id": "PRP#1", "text": "Proposal", "metadata": {"doc_type": "proposal"}}
    kept = sel.screen([old, new, other, card, record], bundle)
    assert [e["evidence_id"] for e in kept] == ["NEW#2", "PRP#1"]
    assert {x["evidence_id"]: x["reason"].split(":")[0] for x in bundle["selection"]["excluded"]} == {
        "OLD#2": "not_in_force", "NEW#0": "price_row_not_in_play", "CMP#0": "neutral_guidance_not_grounded"}
    assert all(x["stage"] == "agent" for x in bundle["selection"]["excluded"])


def test_screen_changes_nothing_without_a_selection():
    found = [row("X#0", "Nivarque Core", "Starter")]
    assert sel.screen(found, {}) == found


@pytest.mark.parametrize("url, date_known, content, expected", [
    ("https://markets-quotes.example/acme", False, "Acme. Industry: energy. Employees: 1,000.", True),  # E15
    ("https://markets-quotes.example/acme", True, "Acme. Industry: energy. Employees: 1,000.", False),
    ("https://news.example/2026/acme", False, "Acme opened a new plant.", False),  # undated news stays news
])
def test_an_undated_page_on_a_market_data_url_is_a_data_page_not_news(url, date_known, content, expected):
    assert is_data_page("Acme company profile", url, content, undated=not date_known) is expected


# --- the six audited development scenarios ----------------------------------------------------------

@pytest.fixture(scope="module")
def runs():
    dev = h.compile_split("dev")
    by = {sc["id"]: sc for c in dev for sc in c["scenarios"]}
    return {sid: h.run_scenario(by[sid], dev, h.RUNS / "pytest" / "i3" / sid, "news_fixture") for sid in SIX}


def ref(rec, doc, text):
    """The passage ID of `doc` whose text contains `text` (exactly one, as the benchmark's stable references)."""
    hits = [cid for cid, t in rec["full_text"].items() if cid.split("#")[0] == doc and text in t]
    assert len(hits) == 1, (doc, text, hits)
    return hits[0]


def reached(rec, doc, text):
    return ref(rec, doc, text) in rec["drafting_input"]


def test_purposes_are_the_audited_ones(runs):
    assert {sid: r["purpose"] for sid, r in runs.items()} == SIX
    assert all(r["status"] == "briefing_ready" and not r["blocked_connections"] for r in runs.values())


def test_e3_negotiation_receives_the_list_price_of_the_proposed_product_only(runs):
    rec = runs["DEV-P2"]
    assert reached(rec, "NVQ-PRC-2026-v1", "Nivarque Engineering Vault")
    for tier in ("Tier: Starter", "Tier: Business", "Records Retention Add-on"):
        assert not reached(rec, "NVQ-PRC-2026-v1", tier), tier
    assert reached(rec, "NVQ-POL-001", "Discount approval policy")  # the approval thresholds for a price position


def test_e4_e5_the_customers_own_request_reaches_the_drafter(runs):
    assert reached(runs["DEV-L1"], "NVQ-COR-BXL-001", "3 TB")
    assert reached(runs["DEV-C1"], "NVQ-COR-BXC-001", "36-month term")
    assert reached(runs["DEV-P2"], "NVQ-COR-BXP-001", "60 additional users")
    assert reached(runs["DEV-T1"], "NVQ-COR-BXT-001", "8 TB")


def test_e12_commitments_and_proposal_dates_reach_the_drafter(runs):
    assert reached(runs["DEV-P2"], "NVQ-COR-BXP-001", "replied that")
    assert reached(runs["DEV-T1"], "NVQ-PRP-BXT-001", "This proposal was sent")


@pytest.mark.parametrize("sid", ["DEV-P2", "DEV-T1", "DEV-C1", "DEV-L1"])
def test_every_passage_of_the_customers_current_records_reaches_the_drafter(runs, sid):
    rec = runs[sid]
    code = sid[4]
    docs = {f"NVQ-PRP-BX{code}-001", f"NVQ-COR-BX{code}-001"}
    passages = [cid for cid in rec["full_text"] if cid.split("#")[0] in docs]
    assert passages and all(p in rec["drafting_input"] for p in passages)


def test_requested_add_on_is_priced_only_where_the_customer_asked_for_it(runs):
    for sid in ("DEV-T1", "DEV-L1"):
        assert reached(runs[sid], "NVQ-PRC-2026-v1", "Records Retention Add-on"), sid
        assert reached(runs[sid], "NVQ-PRD-001", "Records Retention Add-on applies"), sid
    for sid in ("DEV-P2", "DEV-C1"):
        assert not reached(runs[sid], "NVQ-PRC-2026-v1", "Records Retention Add-on"), sid


def test_e2_product_demo_receives_product_security_and_retention_evidence(runs):
    rec = runs["DEV-M2"]
    for doc, text in [("NVQ-PRD-001", "Records Retention Add-on applies"), ("NVQ-PRD-001", "SAML 2.0"),
                      ("NVQ-PRD-001", "EU and US regions"), ("NVQ-POL-002", "encrypted at rest"),
                      ("NVQ-POL-002", "do not leave that region"), ("NVQ-POL-002", "REST API")]:
        assert reached(rec, doc, text), text
    assert not any(cid.startswith("NVQ-POL-001") for cid in rec["drafting_input"])  # discount policy is not demo


@pytest.mark.parametrize("sid", list(SIX))
def test_every_official_statement_of_a_retrieved_public_source_reaches_the_drafter(runs, sid):
    rec = runs[sid]
    official = f"NVQ-PUB-BX{sid[4]}-001"
    for marker in ("[E1]", "[E2]", "[E3]", "[E4]"):
        assert reached(rec, official, marker), marker  # M2 'digital consent since 2025' was missing in CP-2


def test_demo_surfaces_the_scim_disagreement_as_a_disclosure_never_as_a_fact(runs):
    rec = runs["DEV-M2"]  # the audit's latent issue: both SCIM statements now reach a demo briefing
    assert "conflict:C2" in {d["id"] for d in rec["disclosures"]}
    scim = {ref(rec, "NVQ-PRD-001", "SCIM"), ref(rec, "NVQ-POL-002", "SCIM")}
    facts = [i for items in rec["briefing"].values() for i in items if i["kind"] == "fact"]
    assert not any(scim & set(i["evidence_ids"]) for i in facts)


def test_e7_introduction_receives_the_product_descriptions_for_a_fit_hypothesis(runs):
    rec = runs["DEV-E1"]
    for text in ("Engineering Vault extends", "Nivarque Core is a document", "Records Retention Add-on applies"):
        assert reached(rec, "NVQ-PRD-001", text), text
    # configuration detail is not introduction material (and would raise an unrelated SCIM disclosure)
    assert not reached(rec, "NVQ-PRD-001", "SCIM")
    assert "conflict:C2" not in {d["id"] for d in rec["disclosures"]}


@pytest.mark.parametrize("sid", list(SIX))
def test_e14_no_superseded_price_row_reaches_the_drafter(runs, sid):
    assert not any(cid.startswith("NVQ-PRC-2025") for cid in runs[sid]["drafting_input"])


@pytest.mark.parametrize("sid", list(SIX))
def test_e10_no_unmentioned_competitor_reaches_the_drafter_or_the_briefing(runs, sid):
    rec = runs[sid]  # owner decision: no development scenario's evidence names the competitor
    assert not any(c.startswith("NVQ-CMP-") for c in rec["drafting_input"])
    assert rec["selection"]["competition"]["relevant"] is False
    text = " ".join(e["excerpt"] for e in rec["drafting_input"].values())
    briefing = " ".join(i["text"] for items in rec["briefing"].values() for i in items)
    assert "solquend" not in text.casefold() and "solquend" not in briefing.casefold()
    assert not rec["briefing"]["competitive_positioning"]


def _card(eid, text):
    return {"evidence_id": eid, "text": text, "metadata": {"doc_type": "battlecard"},
            "organizations": [{"org_id": "nivarque", "role": "vendor", "name": "Nivarque Document Systems"},
                              {"org_id": "solquend", "role": "competitor", "name": "Solquend Archive Systems"}]}


def test_battlecard_passages_need_the_competitor_named_in_the_evidence_by_name_or_alias():
    card = _card("CMP#3", "If a prospect says Solquend is cheaper, compare total cost.")
    products = ["Nivarque Engineering Vault"]
    assert sel.battlecard_exclusion(card, "Proposal for Nivarque Engineering Vault.", products) \
        .startswith("competitor_not_named_in_evidence")  # the alias alone counts as naming the competitor
    assert sel.battlecard_exclusion(card, "The buyer also evaluates Solquend.", products) is None
    assert sel.battlecard_exclusion(card, "The buyer also evaluates Solquend Archive Systems.", []) is None


def test_neutral_guidance_is_kept_only_when_it_covers_a_product_in_play():
    neutral = _card("CMP#9", "Compare total cost of Nivarque Engineering Vault including transmittal effort.")
    assert sel.battlecard_exclusion(neutral, "", ["Nivarque Engineering Vault"]) is None
    assert sel.battlecard_exclusion(neutral, "", ["Nivarque Core"]).startswith("neutral_guidance_not_grounded")
    assert sel.battlecard_exclusion(neutral, "", []).startswith("neutral_guidance_not_grounded")


def test_e15_undated_market_data_page_does_not_reach_the_drafter(runs):
    rec = runs["DEV-M2"]
    data = [it for c in h.compile_split("dev") for it in c["news"] if it["role"] == "data_page"
            and it["key"].startswith("BXM")]
    assert data and h.news_id(data[0]["url"]) not in rec["drafting_input"]


@pytest.mark.parametrize("sid", list(SIX))
def test_every_drafting_input_passage_has_a_selection_reason(runs, sid):
    s = runs[sid]["selection"]
    assert set(s["evidence"]) == set(runs[sid]["drafting_input"])
    assert all(why.startswith(REASONS) for why in s["evidence"].values()), s["evidence"]
    assert all(x["reason"] and x["stage"] for x in s["excluded"])
    assert not set(s["evidence"]) & {x["evidence_id"] for x in s["excluded"] if x["stage"] != "agent"}


@pytest.mark.parametrize("sid", list(SIX))
def test_safeguards_are_unchanged(runs, sid):
    rec = runs[sid]
    tokens = rec["tokens"]
    for r in rec["expected"]["must_not_reach_drafter"]:  # stale, look-alike and passing-mention news
        assert tokens[r] not in rec["drafting_input"], r
    text = " ".join(e["excerpt"] for e in rec["drafting_input"].values())
    for phrase in rec["expected"]["history"]["draft_phrases"]:  # unreviewed draft notes
        assert phrase not in text
    for e in rec["drafting_input"].values():  # provenance labels intact
        assert e["provenance_label"].startswith(("PUBLIC SOURCE", "SYNTHETIC"))


def test_an_agent_asking_for_obsolete_or_unrelated_prices_cannot_add_them():
    dev = h.compile_split("dev")
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == "DEV-C1")
    script = iter([{"action": "search_internal", "query": "price list 2025 Starter Business Engineering Vault",
                    "rationale": "compare older list prices"}, {"action": "finish_research"}])
    rec = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "i3" / "agent", "news_fixture",
                         decide=lambda context: next(script))
    assert rec["agent"]["calls_used"] == 1
    assert not any(c.startswith("NVQ-PRC-2025") for c in rec["drafting_input"])
    assert not any(c in rec["drafting_input"] for c in ("NVQ-PRC-2026-v1#0", "NVQ-PRC-2026-v1#1"))
    assert any(x["stage"] == "agent" for x in rec["selection"]["excluded"])
    assert reached(rec, "NVQ-COR-BXC-001", "36-month term")  # mandatory selection is unaffected by the agent


# --- production knowledge base (no benchmark data) ----------------------------------------------------

@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    from deal_prep.kb_index import build_kb_index
    d = tmp_path_factory.mktemp("i3_kb")
    build_kb_index(chroma_dir=d)
    return d


def test_a_competitor_named_in_the_customers_own_records_brings_the_battlecard_and_its_advice(kb):
    """Positive coverage of the customer-named competitor rule (restored after the I3 owner decision)."""
    from deal_prep.demo import OfflineNewsClient, TemplateDrafter
    from deal_prep.pipeline import prepare_briefing
    from deal_prep.web_research import Budget, SearchConfig
    meta = {"meeting_id": "TEST", "document_id": "HIST-TEST", "doc_type": "meeting_record",
            "info_origin": "synthetic_record", "creation_method": "user_entered", "approval_status": "approved",
            "effective_from": "2026-11-01", "customer_org_id": "arup", "conflict_group": "", "scope": "company"}
    label = "SYNTHETIC — not a real business fact · approved meeting record"
    meeting = {"evidence_id": "HIST-TEST#0", "document_id": "HIST-TEST", "info_origin": "synthetic_record",
               "creation_method": "user_entered", "provenance_label": label, "metadata": meta,
               "organizations": [{"org_id": "arup", "role": "customer", "reality": "real"}],
               "text": "Meeting record (2026-11-01): Arup said it is also evaluating Solquend for drawing archives."}
    r = prepare_briefing("Arup", news_client=OfflineNewsClient(), budget=Budget(SearchConfig()),
                         generate=TemplateDrafter(), domain="arup.com", purpose="negotiation", chroma_dir=kb,
                         now=datetime(2026, 11, 6, 12, tzinfo=timezone.utc), history_search=lambda identity: [meeting])
    assert r["status"] in ("briefing_ready", "partial_briefing")
    assert r["selection"]["competition"]["relevant"] is True and "Solquend" in r["selection"]["competition"]["reason"]
    assert any(e.startswith("NVQ-CMP-001") for e in r["evidence_ids"])
    comp = r["briefing"]["competitive_positioning"]  # the template's battlecard item cites the battlecard
    assert comp and all(e.startswith("NVQ-CMP") for item in comp for e in item["evidence_ids"])


def test_draft_records_are_never_included_whole_or_used_for_products_in_play(kb):
    from deal_prep.orchestrator import gather_research
    from deal_prep.demo import OfflineNewsClient
    from deal_prep.web_research import Budget, SearchConfig
    b = gather_research("Arup", news_client=OfflineNewsClient(), budget=Budget(SearchConfig()), domain="arup.com",
                        purpose="negotiation", chroma_dir=kb, now=datetime(2026, 11, 6, 12, tzinfo=timezone.utc))
    chosen = b["selection"]["selected"]
    assert not any(eid.startswith("NVQ-MTG-002") for eid, why in chosen.items() if why.startswith("customer_record"))
    rel = {e["evidence_id"] for e in b["internal"]["relationship_history"]["evidence"]}
    assert {f"NVQ-PRP-002#{i}" for i in range(5)} <= rel and {f"NVQ-MTG-001#{i}" for i in range(4)} <= rel
    assert b["selection"]["products_in_play"] == ["Nivarque Engineering Vault"]
    vendor = {e["evidence_id"] for e in b["internal"]["vendor_products_pricing"]["evidence"]}
    assert "NVQ-PRC-2026-v1#2" in vendor and not any(i.startswith("NVQ-PRC-2025") for i in vendor)
    assert [t for t in b["trace"] if t["stage"] == "purpose_selection"]
