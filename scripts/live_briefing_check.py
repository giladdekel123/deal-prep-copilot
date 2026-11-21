"""Owner-authorized live OpenAI briefing test (ONE briefing, worst-case estimate <= $0.10).

Usage: python scripts/live_briefing_check.py [--with-news] [--company NAME] [--domain DOMAIN] [--purpose PURPOSE]
--with-news uses real Tavily news (max 5 credits per briefing, 50 per day, persisted ledger,
no automatic retry of a failed news request). Without it, live news stays off.
--company/--domain/--purpose select the briefing (default: Arup, arup.com, negotiation). Test-only options
added for the owner-authorized Option B verification (2026-11-06); caps and safeguards are unchanged.
1. Loads OPENAI_API_KEY from .env at runtime (never printed, logged or saved).
2. Verifies both approved models are available (models.retrieve; metadata only, not generation).
3. Runs the free research once to size the real prompts, estimates the worst case (3 agent calls +
   2 drafting calls including the retry) and REFUSES if it exceeds $0.10. The SpendGuard also
   re-checks before every call (per-briefing cap $0.10, daily cap $1).
4. Runs one live briefing (Arup, negotiation; live news off: no Tavily calls).
5. Writes a sanitized summary and the EN/HE PDFs to runs/ (gitignored).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from deal_prep import demo  # noqa: E402
from deal_prep.agent import MAX_SUPPLEMENTAL_CALLS, agent_context  # noqa: E402
from deal_prep.app_service import (TAVILY_LEDGER_PATH, BriefingService, live_news_config,  # noqa: E402
                                   load_tavily_client)
from deal_prep.web_research import PersistentBudget  # noqa: E402
from deal_prep.briefing import build_messages  # noqa: E402
from deal_prep.llm import (AGENT_INSTRUCTIONS, AGENT_MAX_OUTPUT_TOKENS, AGENT_MODEL, DRAFT_MAX_OUTPUT_TOKENS,  # noqa: E402
                           DRAFT_MODEL, load_openai_client)
from deal_prep.orchestrator import gather_research  # noqa: E402
from deal_prep.pdf_export import build_pdf  # noqa: E402
from deal_prep.spend import SpendGuard, estimate_cost  # noqa: E402
from deal_prep.web_research import Budget, SearchConfig  # noqa: E402

TEST_CAP_USD = 0.10
_args = argparse.ArgumentParser(description="One owner-authorized live briefing.")
_args.add_argument("--with-news", action="store_true")
_args.add_argument("--company", default="Arup")
_args.add_argument("--domain", default="arup.com")
_args.add_argument("--purpose", default="negotiation")
ARGS = _args.parse_args()
COMPANY, DOMAIN, PURPOSE = ARGS.company, (ARGS.domain or None), ARGS.purpose
WITH_NEWS = ARGS.with_news
# Upper bound for news text the prompt can gain: 10 results per search (mandatory + up to 3 agent
# searches), each a ~60-word excerpt plus a provenance label with URL (~700 characters).
NEWS_CHARS_ALLOWANCE = (1 + MAX_SUPPLEMENTAL_CALLS) * 10 * 700


def main() -> int:
    client = load_openai_client()
    secrets = [client.api_key]
    news_client = budget = None
    if WITH_NEWS:
        news_client = load_tavily_client(live_news_config())
        secrets.append(news_client._key)
        budget = PersistentBudget(live_news_config(), TAVILY_LEDGER_PATH)
    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # 2. Model availability (metadata lookups only).
    availability = {}
    for model in (DRAFT_MODEL, AGENT_MODEL):
        try:
            availability[model] = client.models.retrieve(model).id
        except Exception as e:  # noqa: BLE001 - report the type and message, never the request
            availability[model] = f"UNAVAILABLE ({type(e).__name__}: {str(e)[:160]})"
    print("Model availability:", json.dumps(availability))
    if any(v.startswith("UNAVAILABLE") for v in availability.values()):
        print("Stopping: a required model is unavailable. No paid call was made.")
        return 2

    # 3. Worst-case estimate from the real prompt sizes (research is free: internal KB, news off).
    service = BriefingService()
    service.ensure_index()
    bundle = gather_research(COMPANY, news_client=demo.OfflineNewsClient(), budget=Budget(SearchConfig()),
                             domain=DOMAIN, purpose=PURPOSE, chroma_dir=service.chroma_dir)
    draft_chars = sum(len(m["content"]) for m in build_messages(bundle))
    agent_chars = len(AGENT_INSTRUCTIONS) + len(json.dumps(agent_context(bundle, [], MAX_SUPPLEMENTAL_CALLS))) * 1.5
    if WITH_NEWS:  # news results are not known before the paid search: assume the maximum
        draft_chars += NEWS_CHARS_ALLOWANCE
        agent_chars += NEWS_CHARS_ALLOWANCE
    retry_chars = draft_chars + DRAFT_MAX_OUTPUT_TOKENS * 4 + 600  # retry resends the prompt plus the bad output
    worst = (MAX_SUPPLEMENTAL_CALLS * estimate_cost(AGENT_MODEL, int(agent_chars), AGENT_MAX_OUTPUT_TOKENS)
             + estimate_cost(DRAFT_MODEL, draft_chars, DRAFT_MAX_OUTPUT_TOKENS)
             + estimate_cost(DRAFT_MODEL, int(retry_chars), DRAFT_MAX_OUTPUT_TOKENS))
    print(f"Worst-case estimate for this briefing: ${worst:.4f} (cap ${TEST_CAP_USD:.2f}); "
          f"draft prompt up to {draft_chars} chars; news {'ON (max 5 Tavily credits)' if WITH_NEWS else 'OFF'}")
    if worst > TEST_CAP_USD:
        print("Refused: the worst-case estimate exceeds the approved test cap. No paid call was made.")
        return 3

    # 4. One live briefing.
    guard = SpendGuard(run_cap_usd=TEST_CAP_USD, daily_cap_usd=1.00)
    result = service._run_live(COMPANY, DOMAIN, PURPOSE, client=client, guard=guard,
                               news_client=news_client, budget=budget)
    news = [{k: e.get(k) for k in ("evidence_id", "provenance_label", "time_window", "excerpt")}
            for e in result.get("evidence", {}).values() if e["evidence_id"].startswith("WEB-")]

    # 5. Sanitized summary + PDFs.
    summary = {
        "run_at_utc": stamp, "company": COMPANY, "domain": DOMAIN, "purpose": PURPOSE, "models": availability,
        "identity": result.get("identity"), "research_status": result.get("research_status"),
        "trace_stages": [{k: t.get(k) for k in ("stage", "topic", "outcome", "results")}
                         for t in result.get("trace", [])],
        "evidence": result.get("evidence", {}),  # sanitized index: ID, origin, label, short excerpt
        "worst_case_estimate_usd": round(worst, 6), "status": result["status"], "labels": result.get("labels"),
        "message": result.get("message"), "details": result.get("details"),
        "citation_issues": result.get("citation_issues", []),
        "usage": {k: v for k, v in result["usage"].items()}, "spent_today_usd": guard.spent_today(),
        "news_trace": [t for t in result.get("trace", []) if t["stage"] in ("external_news", "agent_tool")],
        "news_evidence": news,
        "tavily_credits_today": {str(k): v for k, v in budget.used_today.items()} if budget else None,
        "agent": {"status": (result.get("agent") or {}).get("status"),
                  "history": [{k: h.get(k) for k in ("action", "query", "rationale", "outcome")}
                              for h in (result.get("agent") or {}).get("history", [])]},
        "briefing": result.get("briefing"), "disclosures": result.get("disclosures"),
        "total_ms": result["total_ms"],
    }
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if any(s and s in text for s in secrets):
        print("Refusing to print: output unexpectedly contained the API key.")
        return 4
    (out_dir / f"live_briefing_{stamp}.json").write_text(text, encoding="utf-8")
    if result.get("briefing"):
        for lang in ("en", "he"):
            try:
                data, info = build_pdf(result, result["generation_label"], lang)
            except Exception as e:  # a PDF failure is recorded, never retried as a new briefing
                print(f"PDF {lang}: FAILED ({type(e).__name__}: {e})")
                continue
            (out_dir / f"live_briefing_{stamp}_{lang}.pdf").write_bytes(data)
            print(f"PDF {lang}: {info}")
    print(text)
    print(f"\nSaved: runs/live_briefing_{stamp}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
