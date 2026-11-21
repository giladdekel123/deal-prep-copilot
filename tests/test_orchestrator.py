"""Prompt 04 step 1: deterministic mandatory research (simulated Tavily, temporary local index)."""
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.kb_index import build_kb_index
from deal_prep.orchestrator import gather_research
from deal_prep.web_research import Budget, SearchConfig, TavilyClient, TransportError

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def __call__(self, url, json, headers, timeout):
        self.calls.append(json)
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def news(title, url="https://news.example.com/a", hours=6):
    when = (NOW - timedelta(hours=hours)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {"results": [{"url": url, "title": title, "content": title, "score": 0.9, "published_date": when}]}


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("orchestrator_kb")
    build_kb_index(chroma_dir=d)
    return d


def run(kb, company, transport, domain=None, purpose="general"):
    config = SearchConfig()
    client = TavilyClient("test-key-not-real", post=transport, config=config, sleep=lambda s: None)
    return gather_research(company, news_client=client, budget=Budget(config), domain=domain,
                           purpose=purpose, chroma_dir=kb, now=NOW)


def docs(bundle, topic):
    return {e["document_id"] for e in bundle["internal"][topic]["evidence"]}


def test_complete_bundle_for_registered_company(kb):
    t = FakeTransport(news("Arup wins rail design contract"))
    b = run(kb, "Arup", t, domain="arup.com", purpose="negotiation")
    assert b["status"] == "complete" and b["mandatory"] == {"internal_rag": True, "external_news": True}
    assert b["identity"]["org_id"] == "arup" and b["purpose"] == "negotiation"
    assert set(b["internal"]) == {"vendor_products_pricing", "competition", "company_profile", "relationship_history"}
    assert b["external"]["status"] == "found_48h" and b["external"]["recent_count"] == 1


def test_relationship_evidence_is_synthetic_and_tied_to_that_company_only(kb):
    b = run(kb, "Arup", FakeTransport(news("Arup update")), domain="arup.com")
    ev = b["internal"]["relationship_history"]["evidence"]
    assert ev and all(e["info_origin"] == "synthetic_record" for e in ev)
    assert all(e["metadata"]["customer_org_id"] == "arup" for e in ev)
    assert all(e["provenance_label"].startswith("SYNTHETIC") for e in ev)
    assert docs(b, "relationship_history") <= {"NVQ-PRP-002", "NVQ-MTG-001", "NVQ-MTG-002"}


def test_company_profile_evidence_is_public_and_never_the_lookalike(kb):
    b = run(kb, "Arup", FakeTransport(news("Arup update")), domain="arup.com")
    ev = b["internal"]["company_profile"]["evidence"]
    assert ev and all(e["info_origin"] == "public_source" for e in ev)
    assert all(e["metadata"]["subject_org_id"] == "arup" for e in ev)
    assert "NVQ-PUB-008" not in docs(b, "company_profile")


def test_shikun_binui_proposal_found_by_relationship_search(kb):
    # The R8 Gate 2B miss: relationship questions now search synthetic records only (FR-07).
    b = run(kb, "Shikun & Binui", FakeTransport(news("Shikun & Binui wins tender")))
    assert "NVQ-PRP-001" in docs(b, "relationship_history")
    assert any("400 users" in e["text"] for e in b["internal"]["relationship_history"]["evidence"])


def ranked_ids(bundle, topic):  # what the mandatory ranked search returned, before I3 selection
    return next(t["evidence_ids"] for t in bundle["trace"] if t["stage"] == "internal_rag" and t["topic"] == topic)


def test_vendor_wide_topics_are_global_synthetic_only(kb):
    b = run(kb, "Arup", FakeTransport(news("Arup update")), domain="arup.com")
    ev = b["internal"]["vendor_products_pricing"]["evidence"]
    assert ev and all(e["metadata"]["scope"] == "global" and e["info_origin"] == "synthetic_record" for e in ev)
    # I3 (owner decision): the battlecard is searched, but left out because no Arup evidence names the competitor.
    assert ranked_ids(b, "competition") and all(i.startswith("NVQ-CMP-001") for i in ranked_ids(b, "competition"))
    assert b["internal"]["competition"]["evidence"] == [] and b["selection"]["competition"]["relevant"] is False


def test_competition_topic_returns_only_battlecards(kb):
    # Found by visual PDF inspection: price-list rows used to outrank the battlecard for this topic.
    b = run(kb, "Arup", FakeTransport(news("Arup update")), domain="arup.com")
    ids = ranked_ids(b, "competition")
    assert ids and all(i.startswith("NVQ-CMP-") for i in ids)


def test_battlecard_is_kept_when_the_news_names_the_competitor(kb):
    b = run(kb, "Arup", FakeTransport(news("Arup compares Solquend archive offer")), domain="arup.com")
    assert docs(b, "competition") == {"NVQ-CMP-001"} and b["selection"]["competition"]["relevant"] is True


def test_new_lead_has_explicit_no_relationship_gap(kb):
    b = run(kb, "Ashtrom Group", FakeTransport(news("Ashtrom Group signs port contract")))
    assert b["status"] == "complete" and b["internal"]["relationship_history"]["evidence"] == []
    assert any("No prior relationship records" in g for g in b["gaps"])
    assert docs(b, "company_profile") == {"NVQ-PUB-003"}


def test_ambiguous_company_stops_before_any_search(kb):
    t = FakeTransport()
    b = run(kb, "Arup", t)
    assert b["status"] == "clarification_required" and t.calls == []
    assert b["internal"] == {} and b["mandatory"] == {"internal_rag": False, "external_news": False}
    assert b["candidates"] == ["arup", "arup_laboratories"]


def test_unknown_company_is_externally_grounded_with_internal_gap(kb):  # Prompt 04 step 6a
    b = run(kb, "Teva Pharmaceutical", FakeTransport(news("Teva Pharmaceutical reports results")))
    assert b["status"] == "external_with_internal_gap"
    assert set(b["internal"]) == {"vendor_products_pricing", "competition"}
    assert any("No internal records for 'Teva Pharmaceutical'" in g for g in b["gaps"])


def test_web_failure_gives_partial_internal_only(kb):  # step 6b
    b = run(kb, "Arup", FakeTransport(TransportError(503)), domain="arup.com")
    assert b["status"] == "partial_internal_only"
    # Plain-language wording (Prompt 05): no internal status codes in user-facing gap text.
    assert any("The news search could not be completed" in g and "HTTP 503" in g for g in b["gaps"])
    assert not any("provider_error" in g for g in b["gaps"])
    assert b["internal"]["company_profile"]["evidence"]


def test_both_unavailable_gives_insufficient_sources(kb):  # step 6c
    b = run(kb, "Teva Pharmaceutical", FakeTransport(TransportError(None), TransportError(None)))
    assert b["status"] == "insufficient_sources"


def test_no_news_found_is_a_completed_search_with_gap_not_a_failure(kb):
    b = run(kb, "Arup", FakeTransport({"results": []}, {"results": []}), domain="arup.com")
    assert b["status"] == "complete" and b["external"]["status"] == "not_found"
    assert any("not proof that no news exists" in g for g in b["gaps"])


def test_only_the_company_name_is_sent_to_the_news_provider(kb):
    t = FakeTransport({"results": []}, {"results": []})
    b = run(kb, "Shikun & Binui", t)
    assert [c["query"] for c in t.calls] == ["Shikun & Binui news", "Shikun & Binui news"]
    internal_text = " ".join(e["text"] for topic in b["internal"].values() for e in topic["evidence"])
    assert "400 users" in internal_text  # internal evidence exists...
    assert all("400" not in c["query"] and "Nivarque" not in c["query"] for c in t.calls)  # ...but never leaves


def test_trace_records_every_mandatory_step(kb):
    b = run(kb, "Arup", FakeTransport(news("Arup update")), domain="arup.com")
    internal = [t for t in b["trace"] if t["stage"] == "internal_rag"]
    external = [t for t in b["trace"] if t["stage"] == "external_news"]
    assert {t["topic"] for t in internal} == set(b["internal"]) and len(external) == 1
    assert all("evidence_ids" in t and "elapsed_ms" in t for t in internal)
    assert all("test-key-not-real" not in str(t) for t in b["trace"])


@pytest.mark.parametrize("company, purpose", [("", "general"), ("   ", "general"), ("Arup", "sales_pitch")])
def test_invalid_inputs_rejected(kb, company, purpose):
    with pytest.raises(ValueError):
        run(kb, company, FakeTransport(), domain="arup.com", purpose=purpose)
