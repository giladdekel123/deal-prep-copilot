"""Portfolio Phase 3, Task 1: offline mode reports news as "not searched", never as a failed search.

In the offline demo, live news is disabled by design, so no search is attempted. The briefing must
still be labelled partial and must still disclose that current market intelligence is missing,
but it must not describe the skipped search as a failure. Real news-service failures must still be
reported as failures. Simulated components only: no paid calls, no credentials.
"""
from datetime import datetime, timezone

import pytest

from deal_prep import demo
from deal_prep.app_service import SAVED_MODE_LABEL, BriefingService, load_saved_demo
from deal_prep.kb_index import build_kb_index
from deal_prep.pipeline import MARKET_LABELS, STATUS_TEXT, prepare_briefing
from deal_prep.web_research import (Budget, SearchConfig, TavilyClient, TransportError, identify_company,
                                    research_company_news)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
FAILURE_WORDING = ("failed", "could not be completed", "unavailable")


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("offline_news_kb")
    build_kb_index(chroma_dir=d)
    return d


def visible_texts(result: dict) -> list[str]:
    """Every user-facing text that describes the research outcome (screen header, labels, gaps)."""
    return [STATUS_TEXT[result["status"]], result.get("message", ""), *result["labels"].values(),
            *(d["text"] for d in result["disclosures"])]


def test_offline_news_client_gives_status_disabled_not_a_failure():
    identity = identify_company("Shikun & Binui")["identity"]
    news = research_company_news(identity, demo.OfflineNewsClient(), Budget(SearchConfig()), now=NOW)
    assert news["status"] == "disabled"
    assert news["evidence"] == [] and news["credits_used"] == 0
    assert "not searched" in news["message"] and "offline demo mode" in news["message"]
    assert not any(w in news["message"].lower() for w in FAILURE_WORDING)


def test_live_ai_drafting_news_off_reason_names_its_own_mode():
    """Live AI drafting (news off) uses the same no-news client; its reason must not claim offline demo mode."""
    identity = identify_company("Ashtrom Group")["identity"]
    client = demo.OfflineNewsClient(reason=demo.LIVE_AI_NEWS_OFF)
    news = research_company_news(identity, client, Budget(SearchConfig()), now=NOW)
    assert news["status"] == "disabled" and news["credits_used"] == 0
    assert news["message"] == "News was not searched: live news is not enabled in Live AI drafting mode."
    assert news["trace"][0]["outcome"] == f"skipped: {demo.LIVE_AI_NEWS_OFF}"
    assert "offline" not in news["message"].lower()


def test_saved_demo_uses_the_current_not_searched_wording_and_keeps_its_identity():
    saved = load_saved_demo()
    # Identity of the saved demonstration is preserved.
    assert saved["saved_demo"] is True and saved["mode_label"] == SAVED_MODE_LABEL
    assert saved["created_at"] == "2026-11-06T08:03:56.463045+00:00" and saved["status"] == "partial_briefing"
    assert saved["company_input"] == "Shikun & Binui" and saved["purpose"] == "follow_up"
    # Its news wording is exactly what the current offline demo produces. Since the owner review of
    # 8 November 2026 (Task 2, F5) the reason is given once, inside the partial-research disclosure.
    by_id = {d["id"]: d["text"] for d in saved["disclosures"]}
    assert by_id == {"status": f"Incomplete research: news was not searched ({demo.NEWS_DISABLED}), so this "
                               f"briefing does not include current market intelligence."}
    assert saved["labels"] == {"completeness": "partial: internal sources only",
                               "market_intelligence": MARKET_LABELS["disabled"]}
    news = [t for t in saved["trace"] if t["stage"] == "external_news"]
    assert news and all(t["outcome"] == f"skipped: {demo.NEWS_DISABLED}" for t in news)
    for text in visible_texts(saved):
        for word in FAILURE_WORDING:
            assert word not in text.lower(), f"{word!r} in {text!r}"


@pytest.mark.parametrize("company, domain", [("Shikun & Binui", ""), ("Ashtrom Group", ""), ("Arup", "arup.com")])
def test_offline_briefing_never_describes_skipped_news_as_a_failure(kb, company, domain):
    r, _ = BriefingService(chroma_dir=kb).get(company, domain, "general")
    # Still honestly partial, and the missing news is still disclosed.
    assert r["status"] == "partial_briefing"
    assert r["labels"]["completeness"] == "partial: internal sources only"
    assert r["labels"]["market_intelligence"].startswith("not included")
    assert "not searched" in r["labels"]["market_intelligence"]
    texts = [d["text"] for d in r["disclosures"]]
    assert any("not searched" in t and "offline demo mode" in t for t in texts)
    assert any("does not include current market intelligence" in t for t in texts)
    # But nothing calls the deliberately skipped search a failure.
    for text in visible_texts(r):
        for word in FAILURE_WORDING:
            assert word not in text.lower(), f"{word!r} in {text!r}"


def test_real_news_service_failure_is_still_reported_as_a_failure(kb):
    """Guard: the offline wording must not hide a genuine provider error (passes before and after Task 1)."""
    def always_503(url, json, headers, timeout):
        raise TransportError(503)

    client = TavilyClient("tvly-TEST-NOT-REAL", post=always_503, sleep=lambda s: None)
    r = prepare_briefing("Arup", news_client=client, budget=Budget(SearchConfig()), generate=demo.TemplateDrafter(),
                         domain="arup.com", chroma_dir=kb, now=NOW)
    assert r["status"] == "partial_briefing"
    assert r["labels"]["completeness"] == "partial: internal sources only"
    assert "failed" in r["labels"]["market_intelligence"]
    texts = [d["text"] for d in r["disclosures"]]
    assert any("could not be completed" in t and "HTTP 503" in t for t in texts)
    assert any("the external news search failed" in t for t in texts)
    assert not any("not searched" in t or "offline demo mode" in t for t in texts)
