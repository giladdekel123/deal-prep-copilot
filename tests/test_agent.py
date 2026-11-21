"""Prompt 04 step 2: the bounded agent, driven by simulated model decisions. No paid calls."""
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.agent import MAX_SUPPLEMENTAL_CALLS, agent_context, run_agent
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


class Script:
    """Simulated model: returns queued actions and records every context it was shown."""

    def __init__(self, *actions):
        self.actions, self.contexts = list(actions), []

    def __call__(self, context):
        self.contexts.append(context)
        nxt = self.actions.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("agent_kb")
    build_kb_index(chroma_dir=d)
    return d


def setup(kb, company="Arup", domain="arup.com", extra_responses=(), config=None):
    config = config or SearchConfig()
    t = FakeTransport(news(f"{company} wins design contract"), *extra_responses)
    client = TavilyClient("test-key-not-real", post=t, config=config, sleep=lambda s: None)
    budget = Budget(config)
    bundle = gather_research(company, news_client=client, budget=budget, domain=domain, chroma_dir=kb, now=NOW)
    return bundle, client, budget, t


def go(bundle, script, client, budget, kb):
    return run_agent(bundle, script, news_client=client, budget=budget, chroma_dir=kb, now=NOW)


def test_finish_immediately_uses_no_calls_and_keeps_mandatory_evidence(kb):
    bundle, client, budget, t = setup(kb)
    before = {k: [e["evidence_id"] for e in v["evidence"]] for k, v in bundle["internal"].items()}
    r = go(bundle, Script({"action": "finish_research"}), client, budget, kb)
    assert r["status"] == "finished" and r["calls_used"] == 0 and bundle["supplemental"] == []
    assert {k: [e["evidence_id"] for e in v["evidence"]] for k, v in bundle["internal"].items()} == before


def test_internal_lookup_adds_only_new_supplemental_evidence(kb):
    bundle, client, budget, t = setup(kb)
    # Validation correction (2026-11-14): the discount policy is now selected up front for a customer with a current
    # proposal (Arup), so a discount lookup finds nothing new; this lookup asks for evidence not yet selected.
    r = go(bundle, Script({"action": "search_internal", "query": "where is customer data stored and how is it encrypted",
                           "rationale": "check data residency for the meeting"},
                          {"action": "finish_research"}), client, budget, kb)
    assert r["status"] == "finished" and r["calls_used"] == 1
    step = r["history"][0]
    assert step["outcome"].startswith("ok") and step["evidence_ids"]
    assert {e["evidence_id"] for e in bundle["supplemental"]} == set(step["evidence_ids"])
    assert all(e["metadata"]["scope"] == "global" or "arup" in (e["metadata"]["customer_org_id"],
               e["metadata"]["subject_org_id"]) for e in bundle["supplemental"])


def test_web_lookup_runs_through_guard_budget_and_entity_rules(kb):
    extra = {"results": [
        {"url": "https://news.example.com/hub", "title": "Arup to design transport hub", "content": "...",
         "published_date": (NOW - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")},
        {"url": "https://news.example.com/lab", "title": "ARUP Laboratories expands", "content": "...",
         "published_date": (NOW - timedelta(days=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")}]}
    bundle, client, budget, t = setup(kb, extra_responses=[extra])
    r = go(bundle, Script({"action": "search_web", "query": "Arup transport hub news", "rationale": "gap"},
                          {"action": "finish_research"}), client, budget, kb)
    assert r["calls_used"] == 1 and t.calls[-1]["query"] == "Arup transport hub news"
    assert [e["source_url"] for e in bundle["supplemental"]] == ["https://news.example.com/hub"]
    assert budget.used_this_briefing == 2  # 1 mandatory + 1 supplemental


def test_call_limit_stops_the_agent(kb):
    bundle, client, budget, t = setup(kb)
    script = Script(*[{"action": "search_internal", "query": f"query {i}"} for i in range(10)])
    r = go(bundle, script, client, budget, kb)
    assert r["status"] == "call_limit_reached" and r["calls_used"] == MAX_SUPPLEMENTAL_CALLS
    assert len(script.contexts) == MAX_SUPPLEMENTAL_CALLS  # never asked for a 4th action


def test_identical_failed_request_is_rejected_and_counted(kb):
    bundle, client, budget, t = setup(kb, extra_responses=[TransportError(503)])
    script = Script({"action": "search_web", "query": "Arup bridge news"},
                    {"action": "search_web", "query": "  arup   BRIDGE news "},
                    {"action": "finish_research"})
    r = go(bundle, script, client, budget, kb)
    assert [h["outcome"].split(":")[0] for h in r["history"]] == ["failed", "rejected"]
    assert "identical request already tried" in r["history"][1]["outcome"]
    assert len(t.calls) == 2 and r["calls_used"] == 2  # 1 mandatory + 1 failed web call; repeat never sent


@pytest.mark.parametrize("action", [{"action": "write_record", "query": "x"}, {"action": "run_shell"},
                                    {"action": "mark_signed"}, "not a dict", None])
def test_unknown_action_stops_agent_without_side_effects(kb, action):
    bundle, client, budget, t = setup(kb)
    r = go(bundle, Script(action), client, budget, kb)
    assert r["status"] == "stopped: invalid action" and bundle["supplemental"] == []
    assert len(t.calls) == 1  # only the mandatory search


@pytest.mark.parametrize("query, reason", [
    ("Nivarque Arup proposal", "fictional organization"),
    ("Arup NVQ-PRP-002 price", "internal document ID"),
    ("Engineering Vault 46 USD per user", "must name the target company"),
    ("Arup " + "word " * 12, "longer than"),
])
def test_unsafe_or_off_target_web_queries_rejected_before_sending(kb, query, reason):
    bundle, client, budget, t = setup(kb)
    r = go(bundle, Script({"action": "search_web", "query": query}, {"action": "finish_research"}), client, budget, kb)
    assert reason in r["history"][0]["outcome"] and len(t.calls) == 1
    assert r["calls_used"] == 1  # the rejected attempt still counts


def test_tavily_budget_shared_with_mandatory_search(kb):
    bundle, client, budget, t = setup(kb, config=SearchConfig(credits_per_briefing=1))
    r = go(bundle, Script({"action": "search_web", "query": "Arup news today"}, {"action": "finish_research"}),
           client, budget, kb)
    assert "per-briefing cap" in r["history"][0]["outcome"] and len(t.calls) == 1


def test_model_failure_stops_agent_but_keeps_bundle_usable(kb):
    bundle, client, budget, t = setup(kb)
    r = go(bundle, Script(RuntimeError("model unavailable")), client, budget, kb)
    assert r["status"] == "agent_error: RuntimeError" and bundle["status"] == "complete"


def test_agent_not_run_without_usable_research(kb):
    config = SearchConfig()
    client = TavilyClient("test-key-not-real", post=FakeTransport(), config=config)
    bundle = gather_research("Arup", news_client=client, budget=Budget(config), chroma_dir=kb, now=NOW)
    script = Script()
    r = go(bundle, script, client, Budget(config), kb)
    assert r["status"] == "not_run (clarification_required)" and script.contexts == []


def test_context_is_sanitized_and_labels_every_evidence_item(kb):
    bundle, client, budget, t = setup(kb, company="Shikun & Binui", domain=None)
    script = Script({"action": "finish_research"})
    go(bundle, script, client, budget, kb)
    ctx = script.contexts[0]
    assert "test-key-not-real" not in str(ctx)
    assert ctx["evidence"] and all(e["provenance_label"] and e["info_origin"] for e in ctx["evidence"])
    assert all(len(e["excerpt"].split()) <= 61 for e in ctx["evidence"])
    assert "untrusted evidence" in ctx["rules"]


def test_prompt_injection_in_evidence_cannot_trigger_an_action(kb):
    bundle, client, budget, t = setup(kb, company="Shikun & Binui", domain=None)
    # Make sure the injection fixture is visible to the model, as it would be in a real run.
    go(bundle, Script({"action": "search_internal", "query": "follow-up email on the proposal"},
                      {"action": "finish_research"}), client, budget, kb)
    ctx_text = str(agent_context(bundle, [], 1))
    assert "ignore all previous instructions" in ctx_text  # the text reached the model as evidence...
    obeying = Script({"action": "mark_signed", "query": "NVQ-PRP-001"})  # ...a model that obeys it
    r = go(bundle, obeying, client, budget, kb)
    assert r["status"] == "stopped: invalid action"  # ...is stopped by code
