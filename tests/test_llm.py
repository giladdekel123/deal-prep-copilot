"""Real OpenAI adapters and spending guard, tested with a simulated client (no network, no key, no cost)."""
import json
from types import SimpleNamespace

import pytest

from deal_prep import llm
from deal_prep.app_service import BriefingService, available_modes
from deal_prep.demo import TemplateDrafter
from deal_prep.kb_index import build_kb_index
from deal_prep.llm import (AGENT_MODEL, DRAFT_MODEL, OpenAIAgentDecider, OpenAIDrafter, extract_json_text,
                           load_openai_client)
from deal_prep.spend import PRICES, SpendGuard, SpendLimitExceeded, actual_cost, estimate_cost


class FakeResponses:
    """Stands in for client.responses: records kwargs, returns SDK-shaped responses."""

    def __init__(self, reply, usage=(1200, 300), status="completed"):
        self.reply, self.usage, self.status, self.calls = reply, usage, status, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.reply(kwargs) if callable(self.reply) else self.reply
        return SimpleNamespace(
            output_text=text, status=self.status,
            incomplete_details=SimpleNamespace(reason="max_output_tokens") if self.status == "incomplete" else None,
            usage=SimpleNamespace(input_tokens=self.usage[0], output_tokens=self.usage[1],
                                  input_tokens_details=SimpleNamespace(cached_tokens=0),
                                  output_tokens_details=SimpleNamespace(reasoning_tokens=40)))


def fake_client(reply, **kw):
    return SimpleNamespace(responses=FakeResponses(reply, **kw))


@pytest.fixture()
def guard(tmp_path):
    return SpendGuard(run_cap_usd=0.10, daily_cap_usd=1.00, ledger_path=tmp_path / "ledger.json")


# --- request shape and parsing ---------------------------------------------------------------

def test_drafter_sends_guarded_low_effort_request_and_strips_fences(guard):
    client = fake_client('Here you go:\n```json\n{"sections": {}}\n```')
    out = OpenAIDrafter(client, guard)([{"role": "system", "content": "RULES"},
                                        {"role": "user", "content": "{\"company\": \"Arup\"}"}])
    call = client.responses.calls[0]
    assert call["model"] == DRAFT_MODEL == "gpt-6.1-terra" and call["store"] is False
    assert call["reasoning"] == {"effort": "low"} and call["max_output_tokens"] == 4000
    assert call["instructions"] == "RULES" and call["input"] == [{"role": "user", "content": "{\"company\": \"Arup\"}"}]
    assert "text" not in call  # JSON requested via instructions, not an undocumented format option
    assert out["content"] == '{"sections": {}}'
    assert out["usage"]["input_tokens"] == 1200 and out["usage"]["reasoning_tokens"] == 40


def test_agent_decider_uses_luna_and_returns_action_with_usage(guard):
    client = fake_client('{"action": "finish_research"}', usage=(900, 30))
    action = OpenAIAgentDecider(client, guard)({"company": "Arup", "evidence": []})
    assert client.responses.calls[0]["model"] == AGENT_MODEL == "gpt-6-luna"
    assert client.responses.calls[0]["max_output_tokens"] == 600
    assert action == {"action": "finish_research", "_usage": {"input_tokens": 900, "output_tokens": 30}}


@pytest.mark.parametrize("reply", ["not json", "[1, 2]", ""])
def test_agent_invalid_output_becomes_an_unknown_action_that_stops_the_agent(guard, reply):
    action = OpenAIAgentDecider(fake_client(reply), guard)({"company": "Arup"})
    assert action["action"] == "invalid_model_output"


@pytest.mark.parametrize("text, expected", [
    ('{"a": 1}', '{"a": 1}'), ('```json\n{"a": 1}\n```', '{"a": 1}'), ('```\n{"a": 1}\n```', '{"a": 1}'),
    ('Sure! {"a": {"b": 2}} Done.', '{"a": {"b": 2}}'), ("no json", "no json"),
])
def test_extract_json_text(text, expected):
    assert extract_json_text(text) == expected


def test_incomplete_response_reason_is_recorded(guard):
    client = fake_client('{"sections"', status="incomplete")
    out = OpenAIDrafter(client, guard)([{"role": "system", "content": "R"}, {"role": "user", "content": "x"}])
    assert out["usage"]["incomplete_reason"] == "max_output_tokens"


# --- spending guard ---------------------------------------------------------------------------

def test_cost_math_matches_published_prices():
    assert actual_cost("gpt-6.1-terra", {"input_tokens": 8000, "output_tokens": 1500}) == pytest.approx(0.0155)
    assert actual_cost("gpt-6-luna", {"input_tokens": 1_000_000, "output_tokens": 0}) == pytest.approx(0.10)
    assert actual_cost("gpt-6.1-terra", {"input_tokens": 1000, "cached_input_tokens": 1000, "output_tokens": 0}) \
        == pytest.approx(1000 / 1e6 * 0.05)
    assert estimate_cost("gpt-6.1-terra", 30_000, 4000) == pytest.approx(10_000 / 1e6 + 4000 * 5 / 1e6)


def test_call_over_the_per_briefing_cap_is_refused_before_sending(tmp_path):
    tight = SpendGuard(run_cap_usd=0.001, ledger_path=tmp_path / "l.json")
    client = fake_client("{}")
    with pytest.raises(SpendLimitExceeded, match="per-briefing cap"):
        OpenAIDrafter(client, tight)([{"role": "system", "content": "R"}, {"role": "user", "content": "x"}])
    assert client.responses.calls == [] and not (tmp_path / "l.json").exists()


def test_daily_cap_counts_earlier_spending_from_the_ledger(tmp_path):
    g = SpendGuard(ledger_path=tmp_path / "l.json")
    (tmp_path / "l.json").write_text(json.dumps({g._today(): {"usd": 0.995, "calls": 40}}), encoding="utf-8")
    client = fake_client("{}")
    with pytest.raises(SpendLimitExceeded, match="daily cap"):
        OpenAIDrafter(client, g)([{"role": "system", "content": "R"}, {"role": "user", "content": "x"}])
    assert client.responses.calls == []


def test_unpriced_model_is_refused(guard):
    with pytest.raises(SpendLimitExceeded, match="no approved price"):
        OpenAIDrafter(fake_client("{}"), guard, model="gpt-unknown")([{"role": "system", "content": "R"},
                                                                       {"role": "user", "content": "x"}])


def test_actual_spend_recorded_in_run_total_and_daily_ledger(guard):
    d = OpenAIDrafter(fake_client("{}", usage=(8000, 1500)), guard)
    d([{"role": "system", "content": "R"}, {"role": "user", "content": "x"}])
    d([{"role": "system", "content": "R"}, {"role": "user", "content": "y"}])
    assert guard.run_spent_usd == pytest.approx(0.031)
    assert guard.spent_today() == pytest.approx(0.031) and len(guard.calls) == 2
    assert all(c["actual_usd"] <= c["estimate_usd"] for c in guard.calls)  # estimate is an upper bound here


def test_approved_prices_are_the_documented_ones():
    assert PRICES["gpt-6.1-terra"] == {"input": 1.00, "cached_input": 0.05, "output": 5.00}
    assert PRICES["gpt-6-luna"] == {"input": 0.10, "cached_input": 0.01, "output": 0.50}


# --- key handling and mode availability ----------------------------------------------------------

def test_client_built_from_environment_without_retries_or_echo(monkeypatch):
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-NOT-A-REAL-KEY-123456")
    client = load_openai_client()  # constructing a client makes no network call
    assert client.max_retries == 0 and client.timeout == llm.REQUEST_TIMEOUT_S


def test_missing_key_gives_clear_error(monkeypatch):
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        load_openai_client()


def test_live_mode_offered_only_when_a_key_is_available(monkeypatch):
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert list(available_modes()) == ["offline_demo"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-NOT-A-REAL-KEY-123456")
    assert list(available_modes()) == ["offline_demo", "live_ai"]


# --- end to end through the validated pipeline (simulated client) ----------------------------------

@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("llm_kb")
    build_kb_index(chroma_dir=d)
    return d


def simulated_openai():
    """Agent calls get 'finish'; drafting calls get a rule-abiding draft (fenced JSON) built from the payload."""
    drafter = TemplateDrafter()

    def reply(kwargs):
        if kwargs["model"] == AGENT_MODEL:
            return '{"action": "finish_research", "rationale": "mandatory evidence is sufficient"}'
        return "```json\n" + drafter([{"role": "system", "content": kwargs["instructions"]}, *kwargs["input"]]) + "\n```"
    return fake_client(reply, usage=(7000, 1800))


def test_live_mode_end_to_end_with_simulated_openai(kb, guard):
    client = simulated_openai()
    r = BriefingService(chroma_dir=kb)._run_live("Arup", "arup.com", "negotiation", client=client, guard=guard)
    assert r["status"] == "partial_briefing" and r["briefing"]  # partial: live news is off by instruction
    models = [c["model"] for c in client.responses.calls]
    # I3.1: the simulated drafter (the offline template) leaves an essential topic unaddressed, so live mode makes
    # its one coverage repair call; the repeat adds nothing and the valid first draft is kept. Both are metered.
    assert models == [AGENT_MODEL, DRAFT_MODEL, DRAFT_MODEL]
    assert r["coverage"]["repaired"] is False and r["coverage"]["counts"]["missing"] >= 1
    assert r["usage"]["model_calls"] == {"agent": 1, "draft": 2}
    one = {"input_tokens": 7000, "output_tokens": 1800}
    assert r["usage"]["openai_actual_usd"] == pytest.approx(actual_cost(AGENT_MODEL, one) + 2 * actual_cost(DRAFT_MODEL, one))
    assert r["usage"]["tavily_credits"] == 0 and "gpt-6.1-terra" in r["generation_label"]


def test_live_ai_without_news_reports_news_as_not_searched_in_this_mode(kb, guard):
    """Portfolio Phase 3 Task 1: news off in Live AI drafting mode is disclosed accurately, not as a failure
    and not as offline demo mode (simulated OpenAI client; no network)."""
    from deal_prep.pipeline import STATUS_TEXT
    r = BriefingService(chroma_dir=kb)._run_live("Arup", "arup.com", "negotiation", client=simulated_openai(),
                                                 guard=guard)
    assert r["status"] == "partial_briefing" and r["labels"]["completeness"] == "partial: internal sources only"
    texts = [d["text"] for d in r["disclosures"]]
    # Owner review F5 (8 November 2026): the reason is given once, inside the partial-research disclosure.
    assert ("Incomplete research: news was not searched (live news is not enabled in Live AI drafting mode), so "
            "this briefing does not include current market intelligence.") in texts
    assert any("does not include current market intelligence" in t for t in texts)
    assert "not searched" in r["labels"]["market_intelligence"]
    shown = " ".join([STATUS_TEXT[r["status"]], *r["labels"].values(), *texts]).lower()
    for word in ("offline demo", "failed", "could not be completed", "unavailable"):
        assert word not in shown, word
    news = [t for t in r["trace"] if t["stage"] == "external_news"]
    assert news and all(t["outcome"] == "skipped: live news is not enabled in Live AI drafting mode" for t in news)


def test_spend_refusal_produces_clear_no_briefing_without_calling_the_model(kb, tmp_path):
    client = simulated_openai()
    tight = SpendGuard(run_cap_usd=0.0001, ledger_path=tmp_path / "l.json")
    r = BriefingService(chroma_dir=kb)._run_live("Arup", "arup.com", "negotiation", client=client, guard=tight)
    assert r["status"] == "error" and r["message"].startswith("The approved spending limit would have been exceeded")
    assert client.responses.calls == [] and r["usage"]["openai_actual_usd"] == 0
