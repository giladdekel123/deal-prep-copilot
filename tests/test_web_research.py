"""Prompt 03 steps 2–6 with simulated Tavily responses only. No live calls, no credentials."""
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep import web_research as wr
from deal_prep.web_research import (NOT_FOUND_MESSAGE, Budget, BudgetExceeded, CompanyIdentity,
                                    SearchConfig, TavilyClient, TransportError, UnsafeQuery,
                                    assert_query_safe, classify_window, identify_company,
                                    research_company_news)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def rfc(dt):  # Tavily-style RFC 2822 date
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def item(url, title, content="", published=None, score=0.8):
    return {"url": url, "title": title, "content": content, "score": score,
            "published_date": rfc(published) if isinstance(published, datetime) else published}


class FakeTransport:
    """Replays queued responses (dict) or errors (TransportError); records every request."""

    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def __call__(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def make(transport, config=None):
    config = config or SearchConfig()
    sleeps = []
    client = TavilyClient("test-key-not-real", post=transport, config=config, sleep=sleeps.append)
    return client, Budget(config), sleeps


def arup():
    return identify_company("Arup", domain="arup.com")["identity"]


# --- step 2: company identity -------------------------------------------------------

def test_ambiguous_name_requires_clarification_and_no_search():
    r = identify_company("Arup")
    assert r["status"] == "clarification_required" and r["candidates"] == ["arup", "arup_laboratories"]
    assert r["identity"] is None


def test_registry_identity_is_grounded_with_domain_and_lookalikes():
    ident = arup()
    assert (ident.org_id, ident.domain, ident.confidence) == ("arup", "arup.com", "registry")
    assert ident.lookalikes == ("ARUP Laboratories",)


def test_unregistered_company_allowed_but_name_only():
    r = identify_company("Teva Pharmaceutical")
    assert r["status"] == "unregistered" and r["identity"].confidence == "name_only"
    assert r["identity"].org_id is None


def test_lookalike_result_excluded_and_official_source_marked_primary():
    t = FakeTransport({"results": [
        item("https://www.arup.com/news/new-office", "Arup opens new office", "Arup announced...", NOW - timedelta(hours=5)),
        item("https://news.example.com/lab", "ARUP Laboratories expands testing", "ARUP Laboratories in Utah...",
             NOW - timedelta(hours=3)),
        item("https://press.example.org/x", "Unrelated infrastructure story", "No company named", NOW - timedelta(hours=2)),
    ]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "found_48h"
    assert [e["source_url"] for e in out["evidence"]] == ["https://www.arup.com/news/new-office"]
    ev = out["evidence"][0]
    assert ev["entity_match"] == "official_source" and ev["verification_status"] == "primary"
    assert "company's own published claim" in " ".join(ev["limitations"])
    assert out["excluded"]["lookalike"] == 1 and out["excluded"]["uncertain"] == 1


# --- step 3: 48-hour search, 30-day fallback ----------------------------------------

def test_recent_result_found_in_one_call_with_expected_payload():
    t = FakeTransport({"results": [item("https://news.example.com/a", "Arup wins design contract",
                                        "Arup has won...", NOW - timedelta(hours=20))]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "found_48h" and out["recent_count"] == 1 and out["credits_used"] == 1
    payload = t.calls[0]["json"]
    assert payload == {"query": "Arup news", "topic": "news", "search_depth": "basic", "max_results": 10,
                       "include_raw_content": False, "filter_by_published_date": False,
                       "start_date": "2026-11-04", "end_date": "2026-11-06"}
    assert "auto_parameters" not in payload and len(t.calls) == 1


def test_fallback_to_30_days_when_no_recent_result_and_labelled_as_older_context():
    t = FakeTransport(
        {"results": [item("https://news.example.com/old", "Arup report", "Arup said...", NOW - timedelta(days=3))]},
        {"results": [item("https://news.example.com/old", "Arup report", "Arup said...", NOW - timedelta(days=3)),
                     item("https://news.example.com/very-old", "Arup 2025", "Arup...", NOW - timedelta(days=90))]},
    )
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "fallback_30d_found" and out["credits_used"] == 2
    assert t.calls[1]["json"]["start_date"] == "2026-10-07"
    assert [e["time_window"] for e in out["evidence"]] == ["last_30_days"]
    ev = out["evidence"][0]
    assert ev["from_fallback"] and "last 30 days (older context)" in ev["provenance_label"]
    assert out["recent_count"] == 0 and out["excluded"]["older"] >= 1
    assert "older context" in out["message"]


def test_no_results_reports_not_found_not_proof_of_absence():
    t = FakeTransport({"results": []}, {"results": []})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "not_found" and out["evidence"] == []
    assert out["message"] == NOT_FOUND_MESSAGE and "not proof" in out["message"]


# --- step 4: publication date versus retrieval date ---------------------------------

def test_undated_result_is_never_recent_and_triggers_fallback():
    t = FakeTransport({"results": [item("https://news.example.com/u", "Arup update", "Arup...", None)]},
                      {"results": []})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "not_found" and len(t.calls) == 2
    ev = out["evidence"][0]
    assert ev["time_window"] == "undated" and ev["publication_date"] == "unknown"
    assert ev["publication_date_basis"] == "unknown" and "never treated as recent" in ev["limitations"][0]
    assert out["recent_count"] == 0


@pytest.mark.parametrize("value", ["not a date", "", None])
def test_unparseable_dates_are_undated(value):
    assert classify_window(wr.parse_published(value), NOW, SearchConfig()) == "undated"


def test_future_date_is_not_recent():
    assert classify_window(NOW + timedelta(days=2), NOW, SearchConfig()) == "undated"


def test_iso_and_rfc_dates_both_parse():
    assert wr.parse_published("2026-11-05T09:30:00Z") == datetime(2026, 11, 5, 9, 30, tzinfo=timezone.utc)
    assert wr.parse_published("Thu, 05 Nov 2026 09:30:00 GMT") == datetime(2026, 11, 5, 9, 30, tzinfo=timezone.utc)


def test_window_boundaries():
    cfg = SearchConfig()
    assert classify_window(NOW - timedelta(hours=48), NOW, cfg) == "last_48h"
    assert classify_window(NOW - timedelta(hours=48, minutes=1), NOW, cfg) == "last_30_days"
    assert classify_window(NOW - timedelta(days=30), NOW, cfg) == "last_30_days"
    assert classify_window(NOW - timedelta(days=30, minutes=1), NOW, cfg) == "older"


def test_publication_and_retrieval_dates_kept_separate_with_provider_estimate_label():
    pub = NOW - timedelta(hours=10)
    t = FakeTransport({"results": [item("https://news.example.com/a", "Arup news", "Arup...", pub)]})
    client, budget, _ = make(t)
    ev = research_company_news(arup(), client, budget, now=NOW)["evidence"][0]
    assert ev["publication_date"] == pub.isoformat() and ev["retrieved_at"] == NOW.isoformat()
    assert ev["publication_date_basis"] == "provider_estimated"
    assert "may be a last-updated date" in ev["limitations"][0]


# --- step 5: source provenance and quality -------------------------------------------

def test_evidence_has_full_public_provenance_and_short_excerpt():
    long_text = "Arup " + "word " * 120
    t = FakeTransport({"results": [item("https://news.example.com/a", "Arup story", long_text, NOW - timedelta(hours=1))]})
    client, budget, _ = make(t)
    ev = research_company_news(arup(), client, budget, now=NOW)["evidence"][0]
    assert ev["info_origin"] == "public_source" and ev["creation_method"] == "live_web_retrieval"
    assert ev["organizations"] == [{"org_id": "arup", "name": "Arup", "role": "subject", "reality": "real"}]
    assert ev["source_kind"] == "third_party" and ev["verification_status"] == "single_secondary"
    assert ev["publisher"] == "news.example.com" and ev["source_url"] in ev["provenance_label"]
    assert len(ev["excerpt"].split()) <= 50 and ev["evidence_id"].startswith("WEB-")


def test_duplicate_urls_kept_once():
    r = item("https://news.example.com/a", "Arup story", "Arup...", NOW - timedelta(hours=1))
    t = FakeTransport({"results": [r, dict(r)]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert len(out["evidence"]) == 1 and out["excluded"]["duplicate"] == 1


# --- step 6: outages, retries, timeouts and cost caps ---------------------------------

def test_server_error_is_not_retried_and_reported_as_partial():
    t = FakeTransport(TransportError(503))
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "provider_error" and len(t.calls) == 1
    assert "incomplete" in out["message"] and out["evidence"] == []


def test_network_error_retried_once_then_fails_and_both_attempts_cost():
    t = FakeTransport(TransportError(None), TransportError(None))
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "provider_error" and len(t.calls) == 2 and out["credits_used"] == 2
    assert [tr["attempt"] for tr in out["trace"]] == [1, 2]


def test_rate_limit_honours_retry_after_then_succeeds():
    ok = {"results": [item("https://news.example.com/a", "Arup story", "Arup...", NOW - timedelta(hours=1))]}
    t = FakeTransport(TransportError(429, retry_after="2"), ok)
    client, budget, sleeps = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "found_48h" and sleeps == [2.0] and len(t.calls) == 2


def test_timeout_setting_passed_to_transport():
    t = FakeTransport({"results": []}, {"results": []})
    client, budget, _ = make(t, SearchConfig(timeout_seconds=7.5))
    research_company_news(arup(), client, budget, now=NOW)
    assert all(c["timeout"] == 7.5 for c in t.calls)


def test_per_briefing_cap_blocks_fallback_before_sending():
    t = FakeTransport({"results": []})
    client, budget, _ = make(t, SearchConfig(credits_per_briefing=1))
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "budget_exhausted" and len(t.calls) == 1
    assert "fallback not run" in out["message"]


def test_daily_cap_refuses_before_any_call():
    t = FakeTransport()
    client, budget, _ = make(t, SearchConfig(credits_per_day=3))
    budget.used_today[NOW.date()] = 3
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "budget_exhausted" and t.calls == []


def test_budget_ledger_rules():
    b = Budget(SearchConfig(credits_per_briefing=2, credits_per_day=3))
    b.reserve(2, NOW.date())
    with pytest.raises(BudgetExceeded, match="per-briefing"):
        b.reserve(1, NOW.date())
    b.new_briefing()
    b.reserve(1, NOW.date())
    with pytest.raises(BudgetExceeded, match="per-day"):
        b.reserve(1, NOW.date())


# --- P3-4: nothing internal or synthetic reaches the provider -----------------------

@pytest.mark.parametrize("query", ["Nivarque news", "Solquend Archive Systems news", "NVQ-PRP-002 Arup",
                                   "DMS-PRC-001", "SYNTHETIC RECORD Arup", "Arup\nproposal text", "x" * 200])
def test_unsafe_queries_rejected(query):
    with pytest.raises(UnsafeQuery):
        assert_query_safe(query)


def test_payload_with_unexpected_keys_refused_before_sending():
    t = FakeTransport()
    client, budget, _ = make(t)
    with pytest.raises(UnsafeQuery, match="not allowed"):
        client.search({"query": "Arup news", "include_answer": True}, budget, NOW.date(), [])
    assert t.calls == [] and budget.used_this_briefing == 0


def test_every_sent_query_is_only_company_name_and_news():
    t = FakeTransport({"results": []}, {"results": []})
    client, budget, _ = make(t)
    research_company_news(identify_company("Shikun & Binui")["identity"], client, budget, now=NOW)
    assert [c["json"]["query"] for c in t.calls] == ["Shikun & Binui news", "Shikun & Binui news"]


def test_client_requires_explicit_key_and_never_reads_environment(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "should-not-be-used")
    with pytest.raises(ValueError, match="never reads .env"):
        TavilyClient("", post=FakeTransport())


def test_unregistered_company_matches_by_name_only():
    ident = identify_company("Teva Pharmaceutical")["identity"]
    t = FakeTransport({"results": [
        item("https://news.example.com/t", "Teva Pharmaceutical reports results", "Teva Pharmaceutical...",
             NOW - timedelta(hours=6)),
        item("https://news.example.com/o", "Other company news", "Unrelated", NOW - timedelta(hours=6)),
    ]})
    client, budget, _ = make(t)
    out = research_company_news(ident, client, budget, now=NOW)
    assert out["status"] == "found_48h" and len(out["evidence"]) == 1
    assert out["evidence"][0]["organizations"][0]["org_id"] is None


# --- redirect links (seen in the live check on 2026-11-06) -------------------------------

OPAQUE_GOOGLE = ("https://www.google.com/url?opi=89978449&q=CAESjAEBxCJF1-fuSeZiYVDnk6osYKCCG9G"
                 "&sa=U&ved=2ahUKEwiK2ODz3_KXAxX2GFkF&usg=AOvVaw1ljWq4nYzCymGW")


@pytest.mark.parametrize("url, expected", [
    ("https://news.example.com/a", "https://news.example.com/a"),
    (OPAQUE_GOOGLE, None),
    ("https://www.google.com/url?q=https://www.reuters.com/business/arup-1/&sa=U", "https://www.reuters.com/business/arup-1/"),
    ("https://www.google.com/url?url=https%3A%2F%2Fwww.arup.com%2Fnews%2Fx&sa=U", "https://www.arup.com/news/x"),
    ("https://news.google.com/rss/articles/CBMiXmh0dHBzOi8vd3d3", None),
    ("https://www.google.com/url?q=https://www.google.com/url?q=opaque", None),
    ("https://www.google.com/search?q=arup", None),
])
def test_original_url(url, expected):
    assert wr.original_url(url) == expected


def test_opaque_redirect_excluded_never_becomes_evidence():
    t = FakeTransport({"results": [
        item(OPAQUE_GOOGLE, "Unlocking investment potential of TOD in Vietnam",
             "Jingfeng Xu, country director of Arup Vietnam, discussed...", NOW - timedelta(hours=30)),
        item("https://news.example.com/arup-hub", "Arup to lead design of new transport hub", "Arup will...",
             NOW - timedelta(hours=19)),
    ]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert [e["source_url"] for e in out["evidence"]] == ["https://news.example.com/arup-hub"]
    assert out["excluded"]["unresolved_redirect"] == 1
    assert all(e["publisher"] != "google.com" and "google.com" not in e["source_url"] for e in out["evidence"])


def test_recoverable_redirect_unwrapped_with_real_publisher_and_note():
    wrapped = "https://www.google.com/url?q=https://www.reuters.com/business/arup-1/&sa=U"
    t = FakeTransport({"results": [item(wrapped, "Arup wins contract", "Arup has won...", NOW - timedelta(hours=4))]})
    client, budget, _ = make(t)
    ev = research_company_news(arup(), client, budget, now=NOW)["evidence"][0]
    assert ev["source_url"] == "https://www.reuters.com/business/arup-1/"
    assert ev["publisher"] == "reuters.com" and "reuters.com" in ev["provenance_label"]
    assert "recovered from a redirect link" in " ".join(ev["limitations"])


def test_unwrapped_redirect_to_official_domain_is_company_own():
    wrapped = "https://www.google.com/url?url=https%3A%2F%2Fwww.arup.com%2Fnews%2Fx"
    t = FakeTransport({"results": [item(wrapped, "Arup update", "Arup...", NOW - timedelta(hours=4))]})
    client, budget, _ = make(t)
    ev = research_company_news(arup(), client, budget, now=NOW)["evidence"][0]
    assert ev["entity_match"] == "official_source" and ev["verification_status"] == "primary"


def test_redirect_and_direct_link_to_same_article_deduplicated():
    direct = item("https://www.reuters.com/business/arup-1/", "Arup wins contract", "Arup...", NOW - timedelta(hours=4))
    wrapped = dict(direct, url="https://www.google.com/url?q=https://www.reuters.com/business/arup-1/")
    t = FakeTransport({"results": [direct, wrapped]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert len(out["evidence"]) == 1 and out["excluded"]["duplicate"] == 1


def test_only_opaque_redirects_in_48h_triggers_fallback():
    t = FakeTransport({"results": [item(OPAQUE_GOOGLE, "Arup story", "Arup...", NOW - timedelta(hours=3))]},
                      {"results": [item("https://news.example.com/b", "Arup earlier", "Arup...", NOW - timedelta(days=5))]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "fallback_30d_found" and len(t.calls) == 2
    assert out["recent_count"] == 0 and out["excluded"]["unresolved_redirect"] == 1


# --- tightened company matching (owner request after the live check) ------------------

@pytest.mark.parametrize("url, title, content, expected", [
    # qualifies
    ("https://www.arup.com/news/x", "New office opening", "We are pleased to announce...", "official_source"),
    ("https://careers.arup.com/x", "Join us", "Graduate programme...", "official_source"),
    ("https://news.example.com/a", "Arup wins rail design contract", "The firm will...", "headline"),
    ("https://news.example.com/b", "ARUP WINS RAIL CONTRACT", "...", "headline"),
    ("https://news.example.com/c", "Arup Group reports results", "...", "headline"),
    ("https://news.example.com/d", "Transit plan unveiled",
     "Arup has been appointed to design the scheme. Arup said the work starts in 2027.", "repeated_mention"),
    # rejected: passing mentions (patterns seen in the live check on 2026-11-06)
    ("https://www.bdcnetwork.com/top-110", "Top 110 Government Building Engineering Firms for 2026",
     "Fluor, WSP, Jacobs, Burns & McDonnell, Bowman Consulting Group, Arup US, Kimley-Horn, Michael Baker", "passing_mention"),
    ("https://news.example.com/bsr", "BSR seeks new recruits for independent advisory committee",
     "The committee is chaired by Dr Barbara Lane, who is a fellow at Arup and has nearly 30 years' experience",
     "passing_mention"),
    ("https://news.example.com/e", "Unlocking investment potential of TOD in Vietnam",
     "Jingfeng Xu, country director of Arup Vietnam, discussed key conditions", "passing_mention"),
    # rejected: not named, or only as part of another word
    ("https://news.example.com/f", "Infrastructure spending rises", "Several firms...", "uncertain"),
    ("https://news.example.com/g", "Disarupted supply chains", "Markets disarupted...", "uncertain"),
    # rejected: look-alike, wherever it appears (strict separation)
    ("https://news.example.com/h", "ARUP Laboratories expands testing", "Salt Lake City...", "lookalike"),
    ("https://news.example.com/i", "Arup and ARUP Laboratories in naming mix-up", "...", "lookalike"),
    ("https://news.example.com/j", "Lab news", "Arup said... unrelated to ARUP Laboratories, which...", "lookalike"),
])
def test_entity_match_rules(url, title, content, expected):
    assert wr.entity_match({"url": url, "title": title, "content": content}, arup()) == expected


def test_arup_laboratories_site_never_counts_as_arup():
    assert arup().lookalike_domains == ("aruplab.com",)
    for url in ("https://www.aruplab.com/news/x", "https://ltd.aruplab.com/x"):
        r = {"url": url, "title": "ARUP expands testing capacity", "content": "ARUP said..."}
        assert wr.entity_match(r, arup()) == "lookalike"


def test_arup_site_never_counts_as_arup_laboratories():
    lab = identify_company("ARUP Laboratories")["identity"]
    assert lab.org_id == "arup_laboratories" and lab.domain == "aruplab.com"
    assert lab.lookalikes == ("Arup",) and lab.lookalike_domains == ("arup.com",)
    assert wr.entity_match({"url": "https://www.arup.com/x", "title": "ARUP Laboratories news", "content": ""},
                           lab) == "lookalike"
    assert wr.entity_match({"url": "https://www.aruplab.com/x", "title": "Update", "content": ""}, lab) == "official_source"


@pytest.mark.parametrize("title, content, expected", [
    ("ARUP Laboratories expands testing", "ARUP Laboratories in Salt Lake City...", "headline"),
    ("Utah lab adds capacity", "ARUP Laboratories said... ARUP Laboratories will...", "repeated_mention"),
    ("Arup wins rail design contract", "The engineering firm...", "lookalike"),
    ("ARUP Laboratories and Arup confused", "...", "lookalike"),
])
def test_arup_laboratories_as_target_is_not_swallowed_by_its_lookalike(title, content, expected):
    lab = identify_company("ARUP Laboratories")["identity"]
    assert wr.entity_match({"url": "https://news.example.com/x", "title": title, "content": content}, lab) == expected


def test_live_pattern_replay_keeps_headline_and_official_rejects_passing_mentions():
    t = FakeTransport({"results": [
        item("https://www.bdcnetwork.com/top-110", "Top 110 Government Building Engineering Firms for 2026",
             "Fluor, WSP, Jacobs, Arup US, Kimley-Horn", NOW - timedelta(hours=19)),
        item("https://news.example.com/bsr", "BSR seeks new recruits",
             "chaired by Dr Barbara Lane, who is a fellow at Arup", NOW - timedelta(hours=30)),
        item("https://news.example.com/arup-hub", "Arup to lead design of new transport hub", "The firm...",
             NOW - timedelta(hours=10)),
        item("https://www.arup.com/news/annual-report", "Annual report 2026", "Our year in review...",
             NOW - timedelta(hours=12)),
    ]})
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "found_48h"
    kept = {e["source_url"]: e["entity_match"] for e in out["evidence"]}
    assert kept == {"https://news.example.com/arup-hub": "headline",
                    "https://www.arup.com/news/annual-report": "official_source"}
    assert out["excluded"]["passing_mention"] == 2


def test_only_passing_mentions_in_48h_triggers_fallback_not_false_recent():
    t = FakeTransport(
        {"results": [item("https://news.example.com/list", "Top engineering firms", "... Arup ...", NOW - timedelta(hours=5))]},
        {"results": [item("https://news.example.com/arup-old", "Arup completes bridge", "...", NOW - timedelta(days=6))]},
    )
    client, budget, _ = make(t)
    out = research_company_news(arup(), client, budget, now=NOW)
    assert out["status"] == "fallback_30d_found" and out["recent_count"] == 0
    assert [e["source_url"] for e in out["evidence"]] == ["https://news.example.com/arup-old"]


def test_alias_in_headline_qualifies_for_shikun_binui():
    ident = identify_company("Shikun & Binui")["identity"]
    assert wr.entity_match({"url": "https://news.example.com/s", "title": "Shikun and Binui wins tender",
                            "content": "..."}, ident) == "headline"
    assert wr.entity_match({"url": "https://www.shikunbinui.com/en/news", "title": "Update", "content": ""},
                           ident) == "official_source"


def test_manual_identity_without_registry_still_safe():
    ident = CompanyIdentity(name="Example Engineering Ltd")
    assert wr.build_query(ident) == "Example Engineering Ltd news"
