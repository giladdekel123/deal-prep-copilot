"""Prompt 04 step 4: evidence-ID existence, origin and recency checks (simulated model output only)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.briefing import draft_briefing
from deal_prep.citations import validate_citations
from deal_prep.disclosures import required_disclosures, unresolved_conflicts
from deal_prep.kb_index import build_kb_index
from deal_prep.orchestrator import gather_research
from deal_prep.web_research import Budget, SearchConfig, TavilyClient

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, *responses):
        self.queue = list(responses)

    def __call__(self, url, json, headers, timeout):
        return self.queue.pop(0)


class FakeModel:
    def __init__(self, *outputs):
        self.outputs, self.messages = list(outputs), []

    def __call__(self, messages):
        self.messages.append(messages)
        out = self.outputs.pop(0)
        return out if isinstance(out, str) else json.dumps(out)


def dated(title, url, **age):
    return {"url": url, "title": title, "content": title, "score": 0.9,
            "published_date": (NOW - timedelta(**age)).strftime("%a, %d %b %Y %H:%M:%S GMT")}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("citations_kb")
    build_kb_index(chroma_dir=d)
    news = {"results": [dated("Arup wins rail design contract", "https://news.example.com/recent", hours=6),
                        {"url": "https://news.example.com/undated", "title": "Arup profile feature",
                         "content": "Arup...", "score": 0.5, "published_date": None}]}
    config = SearchConfig()
    client = TavilyClient("test-key-not-real", post=FakeTransport(news), config=config)
    return gather_research("Arup", news_client=client, budget=Budget(config), domain="arup.com",
                           chroma_dir=d, now=NOW)


def ev_id(bundle, topic=None, window=None):
    """First approved evidence outside any UNRESOLVED conflict (so only the rule under test can fire)."""
    if topic:
        unresolved = set(unresolved_conflicts(bundle, NOW.date()))
        return next(e["evidence_id"] for e in bundle["internal"][topic]["evidence"]
                    if e["metadata"]["conflict_group"] not in unresolved and e["metadata"]["approval_status"] == "approved")
    return next(e["evidence_id"] for e in bundle["external"]["evidence"] if e["time_window"] == window)


def conflicted_id(bundle):
    return next(e["evidence_id"] for e in bundle["internal"]["company_profile"]["evidence"]
                if e["metadata"]["conflict_group"] == "PUB-ARUP-TRUST-YEAR")


def fact(text, ids, claim_type):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": claim_type}


def draft(bundle, **overrides):
    sections = {
        "company_overview": [fact("Arup is a global consultancy.", [ev_id(bundle, "company_profile")], "real_world_fact")],
        "recent_developments": [fact("Arup won a rail design contract.", [ev_id(bundle, window="last_48h")], "real_world_fact")],
        "our_relationship": [fact("Synthetic record: proposal sent.", [ev_id(bundle, "relationship_history")], "relationship")],
        "opportunities": [fact("Engineering Vault manages transmittals.", [ev_id(bundle, "vendor_products_pricing")], "vendor_product"),
                          {"kind": "inference", "text": "Rail work may need drawing control.",
                           "evidence_ids": [ev_id(bundle, window="last_48h")]}],
        # I3: Arup's evidence names no competitor, so the battlecard is not in the bundle; cite vendor evidence.
        "competitive_positioning": [{"kind": "recommendation", "text": "Compare total cost.",
                                     "evidence_ids": [ev_id(bundle, "vendor_products_pricing")]}],
        "meeting_recommendations": [{"kind": "recommendation", "text": "Confirm the user count.", "evidence_ids": []}],
    }
    sections.update(overrides)
    return {"sections": sections,
            "disclosures": [{"id": d["id"], "text": d["text"]} for d in required_disclosures(bundle)]}


def codes(result):
    return sorted(x["code"] for x in result["issues"])


# --- direct validation --------------------------------------------------------------

def test_correctly_cited_draft_is_valid(bundle):
    assert validate_citations(draft(bundle), bundle) == {"valid": True, "issues": []}


@pytest.mark.parametrize("bad_id", ["NVQ-PUB-999#0", "WEB-000000000000", "NVQ-PRP-002#99", "", "NVQ-PRP-002"])
def test_invented_or_mistyped_citations_rejected(bundle, bad_id):
    d = draft(bundle, company_overview=[fact("Arup is large.", [bad_id], "real_world_fact")])
    r = validate_citations(d, bundle)
    assert codes(r) == ["nonexistent_citation"] and r["issues"][0]["evidence_id"] == bad_id


def test_invented_citation_rejected_even_on_inferences_and_recommendations(bundle):
    d = draft(bundle, meeting_recommendations=[{"kind": "recommendation", "text": "Ask X.", "evidence_ids": ["MADE-UP-1"]}])
    assert codes(validate_citations(d, bundle)) == ["nonexistent_citation"]


def test_synthetic_evidence_cannot_support_a_real_world_fact(bundle):
    synthetic = ev_id(bundle, "relationship_history")
    d = draft(bundle, company_overview=[fact("Arup moved to trust ownership in 1985.", [synthetic], "real_world_fact")])
    r = validate_citations(d, bundle)
    assert codes(r) == ["origin_violation"] and "needs public_source" in r["issues"][0]["message"]


def test_mixed_citation_flags_only_the_wrong_origin(bundle):
    public, synthetic = ev_id(bundle, "company_profile"), ev_id(bundle, "relationship_history")
    d = draft(bundle, company_overview=[fact("Arup fact.", [public, synthetic], "real_world_fact")])
    r = validate_citations(d, bundle)
    assert [x["evidence_id"] for x in r["issues"]] == [synthetic]


def test_public_evidence_cannot_support_a_relationship_claim(bundle):
    d = draft(bundle, our_relationship=[fact("We sent Arup a proposal.", [ev_id(bundle, "company_profile")], "relationship")])
    # Step 5 adds a second, independent rejection: a public profile is not a record of this relationship.
    assert codes(validate_citations(d, bundle)) == ["not_this_customer", "origin_violation"]


@pytest.mark.parametrize("claim_type", ["vendor_price", "vendor_product"])
def test_public_evidence_cannot_support_vendor_claims(bundle, claim_type):
    d = draft(bundle, opportunities=[fact("Vault costs 52 USD.", [ev_id(bundle, "company_profile")], claim_type)])
    assert codes(validate_citations(d, bundle)) == ["origin_violation"]


def test_synthetic_evidence_cannot_support_public_pricing(bundle):
    d = draft(bundle, opportunities=[fact("Arup's published fee is X.", [ev_id(bundle, "vendor_products_pricing")],
                                          "public_pricing")])
    assert codes(validate_citations(d, bundle)) == ["origin_violation"]


def test_undated_news_cannot_support_a_recent_development(bundle):
    d = draft(bundle, recent_developments=[fact("Arup profile.", [ev_id(bundle, window="undated")], "real_world_fact")])
    r = validate_citations(d, bundle)
    assert codes(r) == ["not_recent_evidence"] and "undated" in r["issues"][0]["message"]


def test_curated_public_snapshot_is_never_a_recent_development(bundle):
    d = draft(bundle, recent_developments=[fact("Arup is a consultancy.", [ev_id(bundle, "company_profile")],
                                                "real_world_fact")])
    r = validate_citations(d, bundle)
    assert codes(r) == ["not_recent_evidence"] and "curated snapshot" in r["issues"][0]["message"]


def test_inferences_are_not_origin_checked(bundle):
    d = draft(bundle, opportunities=[{"kind": "inference", "text": "Given the synthetic proposal, pricing may matter.",
                                      "evidence_ids": [ev_id(bundle, "relationship_history")]}])
    assert validate_citations(d, bundle)["valid"]


def test_agent_supplemental_evidence_is_citable(bundle):
    b = dict(bundle, supplemental=[{**bundle["internal"]["vendor_products_pricing"]["evidence"][0],
                                     "evidence_id": "NVQ-CMP-001#77", "_tool": "search_internal"}])
    d = draft(b, competitive_positioning=[{"kind": "recommendation", "text": "x", "evidence_ids": ["NVQ-CMP-001#77"]}])
    assert validate_citations(d, b)["valid"]
    assert not validate_citations(d, bundle)["valid"]  # the same ID without the supplemental lookup is invented


# --- integration with the drafting call (single controlled retry) ---------------------

def test_invented_citation_gets_one_retry_then_succeeds(bundle):
    bad = draft(bundle, company_overview=[fact("Arup is huge.", ["NVQ-PUB-999#0"], "real_world_fact")])
    model = FakeModel(bad, draft(bundle))
    out = draft_briefing(bundle, model)
    assert out["status"] == "ok" and out["model_calls"] == 2 and out["retried"]
    assert "nonexistent_citation" in model.messages[1][-1]["content"]


def test_persistent_origin_violation_produces_no_briefing(bundle):
    bad = draft(bundle, company_overview=[fact("Arup moved to trust ownership in 1985.",
                                              [ev_id(bundle, "relationship_history")], "real_world_fact")])
    out = draft_briefing(bundle, FakeModel(bad, bad))
    assert out["status"] == "citation_validation_failed" and out["draft"] is None
    assert [x["code"] for x in out["citation_issues"]] == ["origin_violation"]
    assert "no briefing was produced" in out["error"]


def test_schema_requires_claim_type_on_facts(bundle):
    d = draft(bundle)
    del d["sections"]["company_overview"][0]["claim_type"]
    out = draft_briefing(bundle, FakeModel(d, d))
    assert out["status"] == "invalid_model_output" and "claim_type" in out["error"]


@pytest.mark.parametrize("section, claim_type", [("company_overview", "relationship"),
                                                 ("recent_developments", "vendor_price"),
                                                 ("our_relationship", "real_world_fact")])
def test_schema_restricts_claim_types_per_section(bundle, section, claim_type):
    d = draft(bundle)
    d["sections"][section][0]["claim_type"] = claim_type
    out = draft_briefing(bundle, FakeModel(d, d))
    assert out["status"] == "invalid_model_output" and f"{claim_type} facts are not allowed in {section}" in out["error"]
