"""Prompt 03 step 7: owner-authorized live Tavily check (at most 2 basic searches).

Usage: python scripts/live_news_check.py
- Loads TAVILY_API_KEY from .env into this process only; the key is never printed, logged,
  written to disk or included in output (output is checked for it before printing).
- Hard cap: 2 credits, no retries, so at most two requests (48-hour search, then the 30-day
  fallback only if needed). Per-briefing/per-day caps are also enforced by the Budget.
- Writes a sanitized summary to runs/live_news_check_<timestamp>.json (gitignored).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

from deal_prep import web_research as wr  # noqa: E402

MAX_LIVE_CREDITS = 2
COMPANY, DOMAIN = "Arup", "arup.com"


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        print("TAVILY_API_KEY is not set in .env or the environment; no request was sent.")
        return 2

    raw_responses = []

    def recording_post(url, json, headers, timeout):  # records responses, never headers
        response = wr._httpx_post(url, json=json, headers=headers, timeout=timeout)
        raw_responses.append(response)
        return response

    config = wr.SearchConfig(credits_per_briefing=MAX_LIVE_CREDITS, credits_per_day=MAX_LIVE_CREDITS,
                             max_retries=0)
    client = wr.TavilyClient(key, post=recording_post, config=config)
    budget = wr.Budget(config)
    identity = wr.identify_company(COMPANY, domain=DOMAIN)["identity"]
    out = wr.research_company_news(identity, client, budget)

    raw_results = [r for resp in raw_responses for r in resp.get("results", [])]
    summary = {
        "run_at_utc": out["retrieved_at"], "company": identity.name, "org_id": identity.org_id,
        "status": out["status"], "window_used": out["window_used"], "message": out["message"],
        "requests_sent": len(out["trace"]), "credits_used_by_ledger": out["credits_used"],
        "trace": out["trace"],
        "raw": {
            "results_returned": len(raw_results),
            "with_published_date": sum(bool(r.get("published_date")) for r in raw_results),
            "published_date_samples": [r.get("published_date") for r in raw_results[:5]],
            "response_fields": sorted({k for resp in raw_responses for k in resp}),
            "result_fields": sorted({k for r in raw_results for k in r}),
        },
        "excluded": out["excluded"],
        "evidence": [{k: e[k] for k in ("source_url", "title", "publisher", "publication_date",
                                        "publication_date_basis", "time_window", "from_fallback",
                                        "entity_match", "source_kind", "verification_status")}
                     | {"excerpt_first_25_words": " ".join(e["excerpt"].split()[:25])}
                     for e in out["evidence"]],
    }
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if key in text:  # defence in depth: never emit the key
        print("Refusing to print: output unexpectedly contained the API key.")
        return 3

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "runs" / f"live_news_check_{ts}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
