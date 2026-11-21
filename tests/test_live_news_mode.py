"""Live AI + live news mode, tested with simulated Tavily and simulated OpenAI (no network, no keys, no cost)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.app_service import BriefingService, available_modes, live_news_config, load_tavily_client
from deal_prep.kb_index import build_kb_index
from deal_prep.web_research import BudgetExceeded, PersistentBudget, SearchConfig, TavilyClient, TransportError
from deal_prep.spend import SpendGuard
from test_llm import simulated_openai


def news_reply(company="Arup", hours=8):
    when = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {"results": [{"url": "https://news.example.com/arup-hub", "title": f"{company} to design new transport hub",
                         "content": f"{company} has been appointed...", "score": 0.9, "published_date": when}]}


class FakeTransport:
    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def __call__(self, url, json, headers, timeout):
        self.calls.append(json)
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("live_news_kb")
    build_kb_index(chroma_dir=d)
    return d


def run(kb, tmp_path, *responses):
    t = FakeTransport(*responses)
    cfg = live_news_config()
    news = TavilyClient("tvly-TEST-NOT-REAL", post=t, config=cfg)
    budget = PersistentBudget(cfg, tmp_path / "tavily.json")
    guard = SpendGuard(ledger_path=tmp_path / "openai.json")
    r = BriefingService(chroma_dir=kb)._run_live("Arup", "arup.com", "negotiation", client=simulated_openai(),
                                                 guard=guard, news_client=news, budget=budget)
    return r, t, budget


def test_approved_live_news_limits():
    cfg = live_news_config()
    assert (cfg.credits_per_briefing, cfg.credits_per_day, cfg.max_retries) == (5, 50, 0)
    assert (cfg.recent_hours, cfg.fallback_days, cfg.max_results) == (48, 30, 10)


def test_live_news_briefing_is_complete_with_public_news_evidence(kb, tmp_path):
    r, t, budget = run(kb, tmp_path, news_reply())
    assert r["status"] == "briefing_ready" and r["labels"]["market_intelligence"].startswith("current")
    web = [e for e in r["evidence"].values() if e["evidence_id"].startswith("WEB-")]
    assert web and all(e["info_origin"] == "public_source" and e["provenance_label"].startswith("PUBLIC SOURCE")
                       for e in web)
    assert r["usage"]["tavily_credits"] == 1 and t.calls[0]["search_depth"] == "basic"
    assert json.loads((tmp_path / "tavily.json").read_text())[datetime.now(timezone.utc).date().isoformat()] == 1


def test_synthetic_labels_preserved_alongside_live_news(kb, tmp_path):
    r, _, _ = run(kb, tmp_path, news_reply())
    rel_ids = {e for item in r["briefing"]["our_relationship"] for e in item["evidence_ids"]}
    assert rel_ids and all(r["evidence"][e]["info_origin"] == "synthetic_record" for e in rel_ids)
    assert all(r["evidence"][e]["provenance_label"].startswith("SYNTHETIC") for e in rel_ids)


def test_failed_news_request_is_not_retried(kb, tmp_path):
    r, t, _ = run(kb, tmp_path, TransportError(None))
    assert len(t.calls) == 1 and r["status"] == "partial_briefing"
    assert r["usage"]["tavily_credits"] == 1


def test_daily_credit_cap_persists_across_restarts(tmp_path):
    cfg = SearchConfig(credits_per_briefing=5, credits_per_day=3)
    today = datetime.now(timezone.utc).date()
    first = PersistentBudget(cfg, tmp_path / "ledger.json")
    first.reserve(2, today)
    second = PersistentBudget(cfg, tmp_path / "ledger.json")  # e.g. after an app restart
    second.reserve(1, today)
    with pytest.raises(BudgetExceeded, match="per-day"):
        PersistentBudget(cfg, tmp_path / "ledger.json").reserve(1, today)
    assert json.loads((tmp_path / "ledger.json").read_text()) == {today.isoformat(): 3}


def test_refused_reservation_writes_nothing(tmp_path):
    b = PersistentBudget(SearchConfig(credits_per_briefing=1, credits_per_day=50), tmp_path / "l.json")
    b.reserve(1, datetime.now(timezone.utc).date())
    with pytest.raises(BudgetExceeded, match="per-briefing"):
        b.reserve(1, datetime.now(timezone.utc).date())
    assert list(json.loads((tmp_path / "l.json").read_text()).values()) == [1]


def test_tavily_key_loaded_only_from_environment_and_never_echoed(monkeypatch):
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY is not set"):
        load_tavily_client(live_news_config())
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-TEST-NOT-REAL")
    client = load_tavily_client(live_news_config())
    assert client.config.max_retries == 0 and "tvly-TEST-NOT-REAL" not in repr(client.config)


def test_live_news_mode_offered_only_with_both_keys(monkeypatch):
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-NOT-A-REAL-KEY-123456")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "live_ai_news" not in available_modes()
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-TEST-NOT-REAL")
    assert list(available_modes()) == ["offline_demo", "live_ai", "live_ai_news"]
    monkeypatch.delenv("OPENAI_API_KEY")
    assert list(available_modes()) == ["offline_demo"]


def test_no_key_appears_in_the_result(kb, tmp_path):
    r, _, _ = run(kb, tmp_path, news_reply())
    assert "tvly-TEST-NOT-REAL" not in json.dumps(r, default=str)
