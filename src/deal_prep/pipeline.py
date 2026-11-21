"""End-to-end briefing pipeline: failure behaviour, tracing, usage and baseline comparison
(Prompt 04 steps 6–7; spec §6A, FR-10, AT-08, AT-16, AT-19).

prepare_briefing() runs: mandatory research (code) -> optional bounded agent -> one drafting call
-> citation and disclosure checks. Failure behaviour (step 6):
  (a) no internal match      -> partial briefing, externally grounded, gap disclosed
  (b) web search failed      -> partial internal-only briefing, labelled "no current market intelligence"
  (c) both unavailable       -> no briefing; a clear explanation instead of speculation
  (d) invalid model output   -> one controlled retry inside drafting, then a clear error
  plus: ambiguous company    -> clarification request, nothing run;  model failure -> clear error.
Tracing and usage (step 7): every stage is recorded with the run ID, a sanitized query, the agent's
short rationale (never hidden reasoning), outcome, duration and evidence IDs; model token usage is
recorded when the adapter reports it, and cost is an ESTIMATE from a configurable price table.
Credentials never enter the trace; key-like strings are redacted defensively.
"""
import re
import time
import uuid
from datetime import datetime, timezone

from deal_prep import config
from deal_prep.agent import run_agent
from deal_prep.briefing import draft_briefing
from deal_prep.evidence import evidence_index
from deal_prep.orchestrator import add_conflict_sources, gather_research
from deal_prep.selection import report as selection_report

TAVILY_USD_PER_CREDIT = 0.008  # pay-as-you-go rate from the Prompt 03 provider review
_KEY_LIKE = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|tvly-[A-Za-z0-9_-]{6,}|eyJ[A-Za-z0-9_-]{10,}|Bearer\s+\S+)")
MAX_TRACE_TEXT = 200

USER_ERRORS = {  # plain-language messages; technical detail is kept separately in result["details"]
    "invalid_model_output": "The draft was not in the required format, even after one retry, so no briefing was produced.",
    "citation_validation_failed": "The draft cited sources that do not properly support its statements, even after "
                                  "one retry, so no briefing was produced.",
    "model_error": "The language model could not be reached, so no briefing was produced. Please try again later.",
    "spend_limit": "The approved spending limit would have been exceeded, so the language model was not called "
                   "and no briefing was produced.",
    "default": "Something went wrong while preparing the briefing, so no briefing was produced.",
}
STATUS_TEXT = {  # plain-language run outcomes for the user interface
    "briefing_ready": "Briefing ready",
    "partial_briefing": "Partial briefing: some information is not included (see gaps)",
    "no_briefing": "No briefing: not enough reliable sources",
    "clarification_required": "Please clarify which company you mean",
    "error": "No briefing: the draft could not be produced",
}

MARKET_LABELS = {
    "found_48h": "current: news from the last 48 hours",
    "fallback_30d_found": "older context: no news in the last 48 hours; last 30 days shown",
    "not_found": "no relevant news found in the searched sources (not proof that none exists)",
    "disabled": "not included: news was not searched (live news is off)",
}


def _sanitize(value):
    if isinstance(value, str):
        return _KEY_LIKE.sub("[REDACTED]", value)[:MAX_TRACE_TEXT]
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


class Meter:
    """Wraps the model callables to record calls, latency and (if reported) token usage.

    A model adapter may return plain content, or {"content": ..., "usage": {"input_tokens", "output_tokens"}}
    for drafting; for agent decisions an action dict may carry "_usage". Usage is stripped before use.
    """

    def __init__(self):
        self.records = []

    def _record(self, stage, started, outcome, usage):
        self.records.append({"stage": stage, "outcome": outcome,
                             "elapsed_ms": round((time.monotonic() - started) * 1000),
                             "input_tokens": (usage or {}).get("input_tokens"),
                             "output_tokens": (usage or {}).get("output_tokens")})

    def wrap_generate(self, generate):
        def metered(messages):
            started = time.monotonic()
            try:
                reply = generate(messages)
            except Exception as e:
                self._record("llm_draft", started, f"error: {type(e).__name__}", None)
                raise
            if isinstance(reply, dict) and "content" in reply:
                content, usage = reply["content"], reply.get("usage")
            else:
                content, usage = reply, None
            self._record("llm_draft", started, "ok", usage)
            return content
        return metered

    def wrap_decide(self, decide):
        def metered(context):
            started = time.monotonic()
            try:
                action = decide(context)
            except Exception as e:
                self._record("agent_decision", started, f"error: {type(e).__name__}", None)
                raise
            usage = action.pop("_usage", None) if isinstance(action, dict) else None
            self._record("agent_decision", started, "ok", usage)
            return action
        return metered


def _usage(meter, budget, prices):
    tokens_in = [r["input_tokens"] for r in meter.records if r["input_tokens"] is not None]
    tokens_out = [r["output_tokens"] for r in meter.records if r["output_tokens"] is not None]
    calls = {"agent": sum(r["stage"] == "agent_decision" for r in meter.records),
             "draft": sum(r["stage"] == "llm_draft" for r in meter.records)}
    complete = len(tokens_in) == len(meter.records) and len(tokens_out) == len(meter.records)
    model_cost = None
    if prices and complete and meter.records:
        model_cost = 0.0
        for r in meter.records:
            p = prices["agent" if r["stage"] == "agent_decision" else "draft"]
            model_cost += r["input_tokens"] / 1e6 * p["input"] + r["output_tokens"] / 1e6 * p["output"]
    return {"model_calls": calls, "input_tokens": sum(tokens_in), "output_tokens": sum(tokens_out),
            "token_usage_complete": complete,
            "estimated_model_cost_usd": round(model_cost, 6) if model_cost is not None else None,
            "tavily_credits": budget.used_this_briefing,
            "tavily_cost_usd_if_paid": round(budget.used_this_briefing * TAVILY_USD_PER_CREDIT, 4),
            "note": "Costs are estimates from configured prices, not provider invoices."}


def _trace(run_id, bundle, meter):
    entries = [dict(t) for t in bundle.get("trace", [])]
    for h in (bundle.get("agent") or {}).get("history", []):
        entries.append({"stage": "agent_tool", "tool": h["action"], "query": h["query"],
                        "rationale": h.get("rationale", ""), "outcome": h["outcome"],
                        "evidence_ids": h.get("evidence_ids", []), "elapsed_ms": h.get("elapsed_ms")})
    entries += [dict(r) for r in meter.records]
    return [_sanitize({"run_id": run_id, **e}) for e in entries]


def prepare_briefing(company: str, *, news_client, budget, generate, decide=None, domain: str | None = None,
                     purpose: str = "general", chroma_dir=config.CHROMA_DIR, now: datetime | None = None,
                     run_id: str | None = None, prices: dict | None = None, history_search=None,
                     repair_coverage: bool = False) -> dict:
    """Run the whole briefing. `decide=None` runs the fixed-workflow baseline (no agent).
    history_search (optional) adds approved Stage 2 meeting records as labelled synthetic evidence.
    repair_coverage (I3.1): one corrected draft when a valid draft leaves essential topics unaddressed (live AI)."""
    now = now or datetime.now(timezone.utc)
    run_id = run_id or uuid.uuid4().hex[:12]
    started = time.monotonic()
    meter = Meter()
    budget.new_briefing()

    bundle = gather_research(company, news_client=news_client, budget=budget, domain=domain,
                             purpose=purpose, chroma_dir=chroma_dir, now=now, history_search=history_search)
    result = {"run_id": run_id, "company_input": company, "purpose": purpose, "created_at": now.isoformat(),
              "mode": "agent" if decide else "baseline", "research_status": bundle["status"],
              "identity": bundle["identity"], "briefing": None, "disclosures": [], "labels": {},
              "agent": None, "message": ""}

    if bundle["status"] == "clarification_required":
        result.update(status="clarification_required", message=" ".join(bundle["gaps"]))
    else:
        if decide is not None:
            result["agent"] = run_agent(bundle, meter.wrap_decide(decide), news_client=news_client,
                                        budget=budget, chroma_dir=chroma_dir, now=now)
            add_conflict_sources(bundle, chroma_dir, now)  # the agent may have surfaced a new conflict
        drafted = draft_briefing(bundle, meter.wrap_generate(generate), repair_coverage=repair_coverage)
        result["coverage"] = drafted.get("coverage")  # I3.1: essential topics communicated in the final briefing
        result["business_analysis"] = drafted.get("business_analysis")  # I5: calculations, formulas, inputs
        news = bundle.get("external") or {}
        result["labels"] = {
            "completeness": {"complete": "complete",
                             "external_with_internal_gap": "partial: no internal records for this company",
                             "partial_internal_only": "partial: internal sources only",
                             "insufficient_sources": "insufficient sources"}[bundle["status"]],
            "market_intelligence": MARKET_LABELS.get(news.get("status"),
                                                     "not included: the news search failed or was not run"),
        }
        if drafted["status"] == "ok":
            result.update(status="briefing_ready" if bundle["status"] == "complete" else "partial_briefing",
                          briefing=drafted["draft"]["sections"], disclosures=drafted["disclosures"],
                          section_notes=drafted.get("section_notes", {}))  # I6: why a section is empty
        elif drafted["status"] == "no_briefing":
            result.update(status="no_briefing",
                          message="Not enough reliable sources to prepare a briefing: " + " ".join(bundle["gaps"]))
        else:
            result.update(status="error", message=USER_ERRORS.get(drafted["status"], USER_ERRORS["default"]),
                          details=drafted["error"], citation_issues=drafted.get("citation_issues", []))
        result["evidence"] = evidence_index(bundle)  # sanitized: id, origin, label, short excerpt
        result["evidence_ids"] = sorted(result["evidence"])
        result["selection"] = selection_report(bundle)  # I3: why each passage is there; what was left out, why

    result["usage"] = _usage(meter, budget, prices)
    result["trace"] = _trace(run_id, bundle, meter)
    result["total_ms"] = round((time.monotonic() - started) * 1000)
    return result


def run_metrics(result: dict) -> dict:
    """Measured quantities for one run (no quality judgement)."""
    cited = [i for items in (result.get("briefing") or {}).values() for item in items for i in item["evidence_ids"]]
    return {"status": result["status"],
            "evidence_items": len(result.get("evidence_ids", [])),
            "distinct_documents": len({i.split("#")[0] for i in result.get("evidence_ids", [])}),
            "citations": len(cited), "distinct_cited_sources": len({i.split("#")[0] for i in cited}),
            "agent_tool_calls": (result.get("agent") or {}).get("calls_used", 0),
            "tavily_credits": result["usage"]["tavily_credits"],
            "model_calls": sum(result["usage"]["model_calls"].values()),
            "total_ms": result["total_ms"]}


def compare_runs(baseline: dict, agent: dict) -> dict:
    """Side-by-side measured metrics for the fixed workflow and the agent variant (AT-16).
    Reports differences only; it does not decide which is better."""
    b, a = run_metrics(baseline), run_metrics(agent)
    metrics = {k: {"baseline": b[k], "agent": a[k],
                   "delta": (a[k] - b[k]) if isinstance(b[k], (int, float)) and not isinstance(b[k], bool) else None}
               for k in b}
    return {"metrics": metrics,
            "note": "Measured differences only. Whether extra evidence improves grounding needs a separate review; "
                    "with simulated models these numbers test the mechanics, not real agent value."}
