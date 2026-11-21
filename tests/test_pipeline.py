"""Prompt 04 steps 6–7: end-to-end failure behaviour, tracing, usage and baseline comparison.

Simulated Tavily and simulated models only. The simulated drafting model builds a rule-abiding
draft from the evidence it is shown (so tests exercise the real validators end to end).
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.kb_index import build_kb_index
from deal_prep.pipeline import compare_runs, prepare_briefing, run_metrics
from deal_prep.web_research import Budget, SearchConfig, TavilyClient, TransportError

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
FAKE_KEY = "tvly-FAKEKEY1234567890"
PRICES = {"draft": {"input": 1.00, "output": 5.00}, "agent": {"input": 0.10, "output": 0.50}}  # USD per 1M tokens


class FakeTransport:
    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def __call__(self, url, json, headers, timeout):
        self.calls.append(json)
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def news(company, hours=6):
    when = (NOW - timedelta(hours=hours)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {"results": [{"url": "https://news.example.com/a", "title": f"{company} wins design contract",
                         "content": "...", "score": 0.9, "published_date": when}]}


class RuleAbidingModel:
    """Simulated drafting model: builds a valid draft from the evidence and required disclosures."""

    def __init__(self, usage=None, outputs=None):
        self.calls, self.usage, self.outputs = 0, usage, list(outputs or [])

    def __call__(self, messages):
        self.calls += 1
        if self.outputs:
            return self.outputs.pop(0)
        payload = json.loads(messages[1]["content"])
        unresolved = {d["id"].split(":", 1)[1] for d in payload["required_disclosures"] if d["id"].startswith("conflict:")}

        def usable(e):
            return e["conflict_group"] not in unresolved and e["approval_status"] in (None, "approved")

        def pick(cond):
            return next((e["evidence_id"] for e in payload["evidence"] if usable(e) and cond(e)), None)

        sections = {s: [] for s in ("company_overview", "recent_developments", "our_relationship", "opportunities",
                                    "competitive_positioning", "meeting_recommendations")}
        if pub := pick(lambda e: e["source"] == "internal:company_profile"):
            sections["company_overview"].append({"kind": "fact", "text": "Profile fact.", "evidence_ids": [pub],
                                                 "claim_type": "real_world_fact"})
        if web := pick(lambda e: e["time_window"] in ("last_48h", "last_30_days")):
            sections["recent_developments"].append({"kind": "fact", "text": "Recent news.", "evidence_ids": [web],
                                                    "claim_type": "real_world_fact"})
        if rel := pick(lambda e: e["source"] == "internal:relationship_history"):
            sections["our_relationship"].append({"kind": "fact", "text": "Synthetic record.", "evidence_ids": [rel],
                                                 "claim_type": "relationship"})
        if ven := pick(lambda e: e["source"] == "internal:vendor_products_pricing"):
            sections["opportunities"].append({"kind": "fact", "text": "Vendor product.", "evidence_ids": [ven],
                                              "claim_type": "vendor_product"})
        sections["competitive_positioning"].append({"kind": "recommendation", "text": "Compare total cost.", "evidence_ids": []})
        sections["meeting_recommendations"].append({"kind": "recommendation", "text": "Confirm needs.", "evidence_ids": []})
        disclosures = [{"id": d["id"], "text": d["text"]} for d in payload["required_disclosures"]]
        disclosures += [{"id": f"empty_section:{s}", "text": "Nothing supported."} for s, v in sections.items() if not v]
        content = json.dumps({"sections": sections, "disclosures": disclosures})
        return {"content": content, "usage": self.usage} if self.usage else content


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("pipeline_kb")
    build_kb_index(chroma_dir=d)
    return d


def run(kb, company, responses, model=None, decide=None, domain=None, run_id="run-test"):
    config = SearchConfig()
    t = FakeTransport(*responses)
    client = TavilyClient(FAKE_KEY, post=t, config=config, sleep=lambda s: None)
    model = model or RuleAbidingModel()
    out = prepare_briefing(company, news_client=client, budget=Budget(config), generate=model, decide=decide,
                           domain=domain, chroma_dir=kb, now=NOW, run_id=run_id, prices=PRICES)
    return out, model, t


# --- step 6: failure behaviour --------------------------------------------------------

def test_complete_research_gives_ready_briefing_with_canonical_disclosures(kb):
    out, model, _ = run(kb, "Arup", [news("Arup")], domain="arup.com")
    assert out["status"] == "briefing_ready" and out["labels"]["completeness"] == "complete"
    assert out["labels"]["market_intelligence"].startswith("current")
    assert any(d["id"] == "conflict:PUB-ARUP-TRUST-YEAR" for d in out["disclosures"])
    assert set(out["briefing"]) == {"company_overview", "recent_developments", "our_relationship", "opportunities",
                                    "competitive_positioning", "meeting_recommendations"}


def test_a_no_internal_match_gives_partial_externally_grounded_briefing(kb):
    out, _, _ = run(kb, "Teva Pharmaceutical", [news("Teva Pharmaceutical")])
    assert out["status"] == "partial_briefing"
    assert out["labels"]["completeness"] == "partial: no internal records for this company"
    assert any(d["id"] == "status" for d in out["disclosures"])
    assert out["briefing"]["our_relationship"] == []


def test_b_web_failure_gives_internal_only_briefing_without_market_intelligence(kb):
    out, _, _ = run(kb, "Arup", [TransportError(503)], domain="arup.com")
    assert out["status"] == "partial_briefing"
    assert out["labels"]["market_intelligence"].startswith("not included")
    assert out["briefing"]["recent_developments"] == []
    assert any("does not include current market intelligence" in d["text"] for d in out["disclosures"])


def test_c_both_unavailable_gives_no_speculative_briefing(kb):
    out, model, _ = run(kb, "Teva Pharmaceutical", [TransportError(None), TransportError(None)])
    assert out["status"] == "no_briefing" and out["briefing"] is None and model.calls == 0
    assert out["message"].startswith("Not enough reliable sources")


def test_d_invalid_model_output_twice_gives_clear_error(kb):
    out, model, _ = run(kb, "Arup", [news("Arup")], model=RuleAbidingModel(outputs=["oops", "{}"]), domain="arup.com")
    assert out["status"] == "error" and out["briefing"] is None and model.calls == 2
    assert "no briefing was produced" in out["message"]


def test_d_invalid_then_valid_output_recovers_with_one_retry(kb):
    out, model, _ = run(kb, "Arup", [news("Arup")], model=RuleAbidingModel(outputs=["oops"]), domain="arup.com")
    assert out["status"] == "briefing_ready" and model.calls == 2


def test_model_outage_gives_clear_error_not_a_crash(kb):
    def broken(messages):
        raise ConnectionError("model unavailable")
    out, _, _ = run(kb, "Arup", [news("Arup")], model=broken, domain="arup.com")
    assert out["status"] == "error" and out["message"].startswith("The language model could not be reached")
    assert "language model call failed (ConnectionError)" in out["details"]  # technical detail kept separately
    assert any(t["stage"] == "llm_draft" and t["outcome"] == "error: ConnectionError" for t in out["trace"])


def test_ambiguous_company_asks_for_clarification_and_runs_nothing(kb):
    out, model, t = run(kb, "Arup", [])
    assert out["status"] == "clarification_required" and model.calls == 0 and t.calls == []
    assert "ARUP Laboratories" in out["message"] and "arup_laboratories" not in out["message"]


def test_agent_failure_does_not_block_the_briefing(kb):
    def failing_agent(ctx):
        raise RuntimeError("agent model down")
    out, _, _ = run(kb, "Arup", [news("Arup")], decide=failing_agent, domain="arup.com")
    assert out["status"] == "briefing_ready" and out["agent"]["status"] == "agent_error: RuntimeError"


def test_no_news_found_is_disclosed_not_hidden(kb):
    out, _, _ = run(kb, "Arup", [{"results": []}, {"results": []}], domain="arup.com")
    assert out["status"] == "briefing_ready"
    assert "not proof that none exists" in out["labels"]["market_intelligence"]
    assert any("not proof that no news exists" in d["text"] for d in out["disclosures"])


# --- step 7: tracing and usage ---------------------------------------------------------

def test_trace_covers_every_stage_with_run_id(kb):
    # Validation correction (2026-11-14): the discount policy is now selected up front for a customer with a current
    # proposal, so the tool step uses a lookup that still finds new evidence (data residency).
    agent = iter([{"action": "search_internal", "query": "data region and encryption", "rationale": "check residency"},
                  {"action": "finish_research"}])
    out, _, _ = run(kb, "Arup", [news("Arup")], decide=lambda ctx: next(agent), domain="arup.com", run_id="run-42")
    stages = [t["stage"] for t in out["trace"]]
    assert {"internal_rag", "external_news", "agent_decision", "agent_tool", "llm_draft"} <= set(stages)
    assert all(t["run_id"] == "run-42" for t in out["trace"])
    tool = next(t for t in out["trace"] if t["stage"] == "agent_tool")
    assert tool["rationale"] == "check residency" and tool["evidence_ids"] and "elapsed_ms" in tool


def test_trace_never_contains_the_api_key(kb):
    out, _, _ = run(kb, "Arup", [news("Arup")], domain="arup.com")
    assert FAKE_KEY not in json.dumps(out)


def test_key_like_text_in_agent_query_is_redacted(kb):
    agent = iter([{"action": "search_internal", "query": "find tvly-LEAKED12345678 please"}, {"action": "finish_research"}])
    out, _, _ = run(kb, "Arup", [news("Arup")], decide=lambda ctx: next(agent), domain="arup.com")
    text = json.dumps(out["trace"])
    assert "tvly-LEAKED12345678" not in text and "[REDACTED]" in text


def test_usage_tokens_and_estimated_cost(kb):
    model = RuleAbidingModel(usage={"input_tokens": 8000, "output_tokens": 1500})
    out, _, _ = run(kb, "Arup", [news("Arup")], model=model, domain="arup.com")
    u = out["usage"]
    assert u["model_calls"] == {"agent": 0, "draft": 1} and (u["input_tokens"], u["output_tokens"]) == (8000, 1500)
    assert u["estimated_model_cost_usd"] == pytest.approx(0.0155)  # 8000*1/1e6 + 1500*5/1e6
    assert u["tavily_credits"] == 1 and u["tavily_cost_usd_if_paid"] == 0.008
    assert "estimates" in u["note"]


def test_cost_not_estimated_when_token_usage_unknown(kb):
    out, _, _ = run(kb, "Arup", [news("Arup")], domain="arup.com")  # model reports no usage
    assert out["usage"]["token_usage_complete"] is False and out["usage"]["estimated_model_cost_usd"] is None


def test_agent_decision_usage_counted(kb):
    actions = iter([{"action": "finish_research", "_usage": {"input_tokens": 900, "output_tokens": 20}}])
    model = RuleAbidingModel(usage={"input_tokens": 8000, "output_tokens": 1500})
    out, _, _ = run(kb, "Arup", [news("Arup")], model=model, decide=lambda ctx: next(actions), domain="arup.com")
    assert out["usage"]["model_calls"] == {"agent": 1, "draft": 1}
    assert out["usage"]["estimated_model_cost_usd"] == pytest.approx(0.0155 + 900 * 0.10 / 1e6 + 20 * 0.50 / 1e6)


# --- step 7: fixed-workflow baseline versus agent (AT-16) -----------------------------------

def test_baseline_and_agent_compared_on_the_same_fixture(kb):
    base, _, _ = run(kb, "Arup", [news("Arup")], domain="arup.com")
    agent_actions = iter([{"action": "search_internal", "query": "Engineering Vault discount approval rules"},
                          {"action": "search_web", "query": "Arup transport hub news"},
                          {"action": "finish_research"}])
    hub = {"results": [{"url": "https://news.example.com/hub", "title": "Arup to design transport hub", "content": "...",
                        "published_date": (NOW - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")}]}
    agent, _, _ = run(kb, "Arup", [news("Arup"), hub], decide=lambda ctx: next(agent_actions), domain="arup.com")
    cmp = compare_runs(base, agent)["metrics"]
    assert base["mode"] == "baseline" and agent["mode"] == "agent"
    assert cmp["agent_tool_calls"] == {"baseline": 0, "agent": 2, "delta": 2}
    assert cmp["tavily_credits"]["delta"] == 1 and cmp["evidence_items"]["delta"] > 0
    assert cmp["status"]["delta"] is None and cmp["status"]["baseline"] == cmp["status"]["agent"] == "briefing_ready"


def test_comparison_reports_differences_without_declaring_a_winner(kb):
    base, _, _ = run(kb, "Arup", [news("Arup")], domain="arup.com")
    same, _, _ = run(kb, "Arup", [news("Arup")], decide=lambda ctx: {"action": "finish_research"}, domain="arup.com")
    report = compare_runs(base, same)
    assert report["metrics"]["evidence_items"]["delta"] == 0 and report["metrics"]["agent_tool_calls"]["delta"] == 0
    assert "Measured differences only" in report["note"] and "not real agent value" in report["note"]
    assert not any(k in report for k in ("winner", "better", "recommendation"))
    assert set(run_metrics(base)) >= {"citations", "distinct_cited_sources", "tavily_credits", "model_calls", "total_ms"}
