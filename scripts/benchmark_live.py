"""Phase 4.5 CP-0: authorized live OpenAI baseline on DEVELOPMENT benchmark scenarios (FICTIONAL TEST DATA).

Owner authorization (2026-11-09): at most $10 USD of OpenAI spend in total for this experiment; no other paid
service. This script never touches the held-out split.

Usage:
  python scripts/benchmark_live.py --dry-run   # free: offline run that sizes the real prompts and prints estimates
  python scripts/benchmark_live.py             # paid: runs SCENARIOS once each, sequentially

What it runs: the production pipeline (prepare_briefing) with the production OpenAI drafter and agent
(deal_prep.llm, unchanged models, prompts, token ceilings and per-briefing cap), fixture news (0 Tavily credits)
and the scenario's seeded meeting history, inside the isolated benchmark environment.

Cost controls:
  - Per-call: the production SpendGuard refuses any call whose conservative estimate would exceed the production
    per-briefing cap ($0.10) or the daily cap; the experiment uses its own ledger (runs/benchmark_v1/cp0/).
  - Per-experiment: before each scenario the cumulative spend in that ledger plus the worst case of one briefing
    (the per-briefing cap x1.5 for estimation error) must stay below HARD_CAP_USD ($8, a $2 margin below the
    authorization); otherwise the run stops before any further call.
  - Network: only api.openai.com is reachable; every other connection is blocked and recorded.
Outputs (gitignored): runs/benchmark_v1/cp0/<run>/records.json, score.json, summary.md; the API key is never
printed or written (every output is scanned for it before writing).
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_harness as h  # noqa: E402  (offline environment; removes API keys from the environment)
import benchmark_run as run  # noqa: E402
import benchmark_score as s  # noqa: E402

AUTHORIZED_USD = 10.00
HARD_CAP_USD = 8.00
SCENARIOS = ("DEV-P2", "DEV-T1", "DEV-C1", "DEV-L1", "DEV-E1", "DEV-M2")
# Final validation (owner-approved 2026-11-12), only with --all-dev: the other six development scenarios.
EXTRA_DEV = ("DEV-P1", "DEV-T2", "DEV-C2", "DEV-L2", "DEV-E2", "DEV-M1")
USE: tuple = SCENARIOS  # the scenarios this process runs (SCENARIOS, or SCENARIOS + EXTRA_DEV with --all-dev)
CP0 = h.RUNS / "cp0"
LEDGER = CP0 / "spend_ledger.json"
API_HOST = "api.openai.com"
NEWS_MODE = "news_fixture"


class Capture:
    """Records what the production drafter or agent received and returned, without changing it."""

    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def __call__(self, arg):
        rec = {"input": arg}
        try:
            out = self.inner(arg)
            rec["output"] = out
            return out
        except Exception as e:  # recorded, then re-raised unchanged
            rec["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            self.calls.append(rec)


def spent_total(path: Path | None = None) -> float:
    path = path or LEDGER  # read at call time, so the ledger in use is always the one checked
    try:
        return round(sum(d["usd"] for d in json.loads(path.read_text(encoding="utf-8")).values()), 6)
    except FileNotFoundError:
        return 0.0


def chars(messages) -> int:
    return sum(len(m["content"]) for m in messages)


def worst_case(draft_chars: int, repair: bool = False) -> float:
    """Agent calls + draft + one controlled retry, plus (I3.1) one coverage repair when enabled."""
    from deal_prep.agent import MAX_SUPPLEMENTAL_CALLS
    from deal_prep.llm import AGENT_MAX_OUTPUT_TOKENS, AGENT_MODEL, DRAFT_MAX_OUTPUT_TOKENS, DRAFT_MODEL
    from deal_prep.spend import estimate_cost
    retry = draft_chars + DRAFT_MAX_OUTPUT_TOKENS * 4 + 600
    return (MAX_SUPPLEMENTAL_CALLS * estimate_cost(AGENT_MODEL, draft_chars, AGENT_MAX_OUTPUT_TOKENS)
            + estimate_cost(DRAFT_MODEL, draft_chars, DRAFT_MAX_OUTPUT_TOKENS)
            + estimate_cost(DRAFT_MODEL, retry, DRAFT_MAX_OUTPUT_TOKENS)
            + (estimate_cost(DRAFT_MODEL, retry + 3000, DRAFT_MAX_OUTPUT_TOKENS) if repair else 0.0))


def contract_on() -> bool:
    from deal_prep import briefing
    return briefing.CONTRACT_IN_MODEL_INPUT


ONLY: tuple = ()  # --scenarios: a subset of SCENARIOS for a targeted run (e.g. the negative variants)
VARIANTS = ("none", "missing_prices", "ambiguous_terms")
VARIANT = "none"  # set by --variant
DOTENV: Path | None = None  # --dotenv: read the API key from this .env (e.g. the main checkout's, from a worktree)


def selected(compiled):
    by_id = {sc["id"]: sc for c in compiled for sc in c["scenarios"]}
    chosen = [by_id[i] for i in USE if not ONLY or i in ONLY]
    if any(not sc["id"].startswith("DEV-") for sc in chosen):  # only ever the development split
        raise h.IsolationError("only development scenarios may be run")
    return chosen


def apply_variant(name: str) -> None:
    """I5 negative tests, in this process only and in memory only (no file or data is changed): perturb the vendor
    evidence the drafter and the research agent receive, to check that missing or ambiguous commercial evidence
    produces "verify", never a fabricated conclusion.
      missing_prices:  every price-list and policy passage is removed (no list price, no approval policy);
      ambiguous_terms: list prices are restated per site (units incompatible with the per-user proposals), and the
                       discount policy's thresholds no longer meet (up to 15 percent, but above 10 percent needs the
                       regional sales director)."""
    if name == "none":
        return
    from deal_prep import agent, orchestrator

    def perturb(found):
        if name == "missing_prices":
            return [e for e in found if (e.get("metadata") or {}).get("doc_type") not in ("price_list", "policy")]
        out = []
        for e in found:
            meta = e.get("metadata") or {}
            if meta.get("doc_type") == "price_list" and "List price" in (e.get("text") or ""):
                e = {**e, "text": e["text"].replace("per user per month", "per site per month")}
            if meta.get("doc_type") == "policy" and "Discount approval policy" in (e.get("text") or ""):
                e = {**e, "text": "Discount approval policy Account executives may approve discounts of up to 15 "
                                  "percent from the list price. Discounts above 10 percent require written approval "
                                  "from the regional sales director."}
            out.append(e)
        return out

    original_select, original_screen = orchestrator.select_for_purpose, agent.screen

    def select(bundle, chroma_dir, today):
        original_select(bundle, chroma_dir, today)
        vendor = bundle["internal"].get("vendor_products_pricing")
        if vendor is not None:
            vendor["evidence"] = perturb(vendor["evidence"])
        bundle["trace"].append({"stage": "evaluation_variant", "variant": name, "elapsed_ms": 0, "outcome": "ok"})

    orchestrator.select_for_purpose = select
    agent.screen = lambda found, bundle: perturb(original_screen(found, bundle))


def write(path: Path, obj, secrets) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str)
    if any(x and x in text for x in secrets):
        raise RuntimeError(f"refusing to write {path.name}: it unexpectedly contains the API key")
    path.write_text(text, encoding="utf-8")


def dry_run(compiled) -> int:
    from deal_prep import demo
    from deal_prep.app_service import LIVE_RUN_CAP_USD
    total = 0.0
    for sc in selected(compiled):
        cap = Capture(demo.TemplateDrafter())
        h.run_scenario(sc, compiled, CP0 / "dryrun" / sc["id"], NEWS_MODE, generate=cap)
        n = max(chars(c["input"]) for c in cap.calls)
        w = worst_case(n, repair=contract_on())
        total += min(w, LIVE_RUN_CAP_USD)
        print(f"{sc['id']} ({sc['purpose']}): draft prompt {n} chars; worst case ${w:.4f} "
              f"({'within' if w <= LIVE_RUN_CAP_USD else 'ABOVE'} the production per-briefing cap ${LIVE_RUN_CAP_USD:.2f})")
    print(f"Worst case for all {len(selected(compiled))} scenarios (each capped at ${LIVE_RUN_CAP_USD:.2f}): ${total:.4f}; "
          f"experiment hard cap ${HARD_CAP_USD:.2f}; spent so far ${spent_total():.4f}. No paid call was made.")
    return 0


def spent_today(path: Path | None = None) -> float:
    path = path or LEDGER
    try:
        day = datetime.now(timezone.utc).date().isoformat()
        return json.loads(path.read_text(encoding="utf-8")).get(day, {}).get("usd", 0.0)
    except FileNotFoundError:
        return 0.0


def live(compiled, run_cap: float | None = None, tag: str = "", daily_cap: float | None = None) -> int:
    """run_cap: an additional owner authorization for this run only (USD); the run stops before any scenario whose
    worst case could take this run's spend above it. The experiment hard cap still applies."""
    from deal_prep.app_service import LIVE_DAILY_CAP_USD, LIVE_RUN_CAP_USD
    from deal_prep.llm import (AGENT_MAX_OUTPUT_TOKENS, AGENT_MODEL, DRAFT_MAX_OUTPUT_TOKENS, DRAFT_MODEL,
                               OpenAIAgentDecider, OpenAIDrafter, load_openai_client)
    from deal_prep import evidence
    from deal_prep.spend import PRICES, SpendGuard

    os.environ.pop("DEAL_PREP_NO_DOTENV", None)  # let the production loader read .env (never printed)
    if DOTENV:  # read in place (never copied or printed); the production loader does not override it
        from dotenv import load_dotenv
        load_dotenv(DOTENV, override=False)
    client = load_openai_client()
    os.environ.pop("TAVILY_API_KEY", None)  # no other paid service
    os.environ["DEAL_PREP_NO_DOTENV"] = "1"
    secrets = [client.api_key]
    models = {m: client.models.retrieve(m).id for m in (DRAFT_MODEL, AGENT_MODEL)}  # metadata only, free
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + (f"_{tag}" if tag else "")
    out = CP0 / run_id
    run_start = spent_total()
    out.mkdir(parents=True, exist_ok=True)
    config = {"draft_model": DRAFT_MODEL, "agent_model": AGENT_MODEL, "models_retrieved": models,
              "draft_max_output_tokens": DRAFT_MAX_OUTPUT_TOKENS, "agent_max_output_tokens": AGENT_MAX_OUTPUT_TOKENS,
              "reasoning_effort": "low", "store": False, "prices_usd_per_1M": {m: PRICES[m] for m in models},
              "per_briefing_cap_usd": LIVE_RUN_CAP_USD, "daily_cap_usd": LIVE_DAILY_CAP_USD,
              "experiment_hard_cap_usd": HARD_CAP_USD, "authorized_usd": AUTHORIZED_USD, "news": NEWS_MODE,
              "experiment_daily_cap_usd": daily_cap or LIVE_DAILY_CAP_USD,
              "clock": h.CLOCK.isoformat(), "scenarios": list(USE), "run_cap_usd": run_cap,
              "evidence_profile_in_model_input": evidence.PROFILE_IN_MODEL_INPUT,
              "contract_in_model_input": contract_on(), "coverage_repair": contract_on(),
              "i4_enabled": __import__("deal_prep.chronology", fromlist=["ENABLED"]).ENABLED,
              "i5_enabled": __import__("deal_prep.business", fromlist=["ENABLED"]).ENABLED,
              "i6_in_model_input": __import__("deal_prep.briefing", fromlist=["i6_active"]).i6_active(),
              "ledger": LEDGER.as_posix(), "variant": VARIANT, "scenarios_run": [s["id"] for s in selected(compiled)],
              "spent_before_run_usd": run_start}
    print("Config:", json.dumps(config))
    before_fp = run.fingerprint()  # protected local data, checked again after the run
    records, ledger_rows, stop = [], [], None
    for sc in selected(compiled):
        before = spent_total()
        if before + 1.5 * LIVE_RUN_CAP_USD > HARD_CAP_USD:
            stop = f"stopped before {sc['id']}: ${before:.4f} spent; the next briefing could exceed the hard cap"
            break
        if run_cap is not None and (before - run_start) + 1.5 * LIVE_RUN_CAP_USD > run_cap:
            stop = f"stopped before {sc['id']}: ${before - run_start:.4f} spent in this run; the run cap could be exceeded"
            break
        remaining = HARD_CAP_USD - before if run_cap is None else min(HARD_CAP_USD - before, run_cap - (before - run_start))
        guard = SpendGuard(run_cap_usd=LIVE_RUN_CAP_USD,
                           daily_cap_usd=min(daily_cap or LIVE_DAILY_CAP_USD, spent_today() + remaining),
                           ledger_path=LEDGER)
        draft = Capture(OpenAIDrafter(client, guard))
        agent = Capture(OpenAIAgentDecider(client, guard))
        rec = {"scenario": sc["id"], "company": sc["company"], "purpose": sc["purpose"], "error": None}
        try:
            rec.update(h.run_scenario(sc, compiled, out / sc["id"], NEWS_MODE, generate=draft, decide=agent,
                                      prices={"draft": PRICES[DRAFT_MODEL], "agent": PRICES[AGENT_MODEL]},
                                      allow_hosts=(API_HOST,), repair_coverage=contract_on()))
        except Exception as e:  # recorded; cost is bounded per call by the guard
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()
        rec.update(layer="live", openai_calls=guard.calls, actual_usd=round(guard.run_spent_usd, 6),
                   draft_calls=draft.calls, agent_calls=agent.calls)
        records.append(rec)
        row = {"scenario": sc["id"], "calls": len(guard.calls), "actual_usd": rec["actual_usd"],
               "cumulative_usd": spent_total(), "status": rec.get("status"), "error": rec["error"],
               "blocked_connections": len(rec.get("blocked_connections", []))}
        ledger_rows.append(row)
        print(json.dumps(row))
        refused = [c for c in draft.calls + agent.calls if "SpendLimitExceeded" in (c.get("error") or "")]
        rec["refused_calls"] = len(refused)  # production handles a refusal itself; the experiment stops after it
        if refused or (rec["error"] and "SpendLimitExceeded" in rec["error"]):
            stop = f"stopped after {sc['id']}: a spending cap refused a call"
            break
    protected_unchanged = run.fingerprint() == before_fp
    print(f"Protected local data unchanged: {'yes' if protected_unchanged else 'NO'}")
    scored = [r for r in records if not r["error"]]
    aggs = {NEWS_MODE: s.aggregate([s.score_scenario(r) for r in scored])} if scored else {}
    score = {"label": h.LABEL, "run_id": run_id, "layer": "live", "scorer_version": s.SCORER_VERSION,
             "config": config, "ledger": ledger_rows, "protected_unchanged": protected_unchanged,
             "coverage": {r["scenario"]: r.get("coverage") for r in scored},
             "total_usd": spent_total(), "stop": stop, "metrics": aggs,
             "per_scenario": {r["scenario"]: s.score_scenario(r) for r in scored}}
    write(out / "records.json", {"label": h.LABEL, "config": config, "records": records}, secrets)
    write(out / "score.json", score, secrets)
    lines = [f"# CP-0 live baseline {run_id} (development split, LIVE layer) — FICTIONAL TEST DATA", "",
             f"**{h.LABEL}**", "", f"Scenarios run: {len(records)}; scored: {len(scored)}; stop: {stop or 'none'}; "
             f"OpenAI spend recorded: ${spent_total():.4f} of ${AUTHORIZED_USD:.2f} authorized.", ""]
    for mode, agg in aggs.items():
        lines += [f"## Automated metrics ({mode})", ""] + run.table(agg) + [""]
        lines += ["## Failures", ""] + [f"- **{m}** {f}" for m, a in agg.items() for f in a["failures"]] + [""]
        lines += ["## Vacuous passes", ""] + [f"- **{m}** {v}" for m, a in agg.items() for v in a["vacuous"]] + [""]
    write(out / "summary.md", "\n".join(lines), secrets)
    print("\n".join(lines))
    print(f"Saved: {out.relative_to(h.ROOT)}")
    return 0 if not stop and len(scored) == len(selected(compiled)) and protected_unchanged else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-cap", type=float, default=None, help="additional per-run authorization in USD")
    ap.add_argument("--tag", default="", help="suffix for the run folder, e.g. post_i1")
    ap.add_argument("--no-profile", action="store_true",
                    help="CP-2 A/B comparison only: send the evidence without the profile fields")
    ap.add_argument("--no-contract", action="store_true",
                    help="I3.1 A/B comparison only: the I3 drafter (no meeting contract, no coverage repair)")
    ap.add_argument("--daily-cap", type=float, default=None,
                    help="experiment-only daily cap in USD (owner-authorized ceiling); default: the production cap")
    ap.add_argument("--no-i4", action="store_true",
                    help="I4 A/B comparison only: the I3.1 drafter (no derived conflicts, chronology or date rules)")
    ap.add_argument("--no-i5", action="store_true",
                    help="I5 A/B comparison only: the I4 drafter (no business analysis in the model input)")
    ap.add_argument("--variant", default="none", choices=VARIANTS,
                    help="I5 negative test: perturb the commercial evidence in memory (see apply_variant)")
    ap.add_argument("--scenarios", default="", help="comma-separated subset of the six scenarios")
    ap.add_argument("--all-dev", action="store_true",
                    help="final validation: all twelve development scenarios (SCENARIOS + EXTRA_DEV)")
    ap.add_argument("--no-i6", action="store_true",
                    help="I6 A/B comparison only: the I5 drafter (no section-placement and conciseness rules)")
    ap.add_argument("--no-i7", action="store_true",
                    help="controlled comparison: switch off I7 (company context, research coverage, business "
                         "unknowns, dates, news excerpts, length policy)")
    ap.add_argument("--no-conflict-guard", action="store_true",
                    help="controlled comparison: switch off I7.1 (compatibility findings for the drafter and the "
                         "conflict-claim safeguard)")
    ap.add_argument("--dotenv", type=Path, default=None,
                    help="read OPENAI_API_KEY from this .env file (e.g. the main checkout's, when run from a worktree)")
    ap.add_argument("--ledger", type=Path, default=None,
                    help="spend ledger to check and record against (e.g. the main checkout's, so every cap sees all "
                         "experiment spend); default: runs/benchmark_v1/cp0/spend_ledger.json of this checkout")
    args = ap.parse_args(argv)
    from deal_prep import briefing, business, chronology, company_context, conflict_guard, contract
    conflict_guard.ENABLED = not args.no_conflict_guard  # the prompt edit takes effect only with I6 (guard_active)
    briefing.CONTRACT_IN_MODEL_INPUT = not args.no_contract  # this process only
    chronology.ENABLED = not args.no_i4 and not args.no_contract
    business.ENABLED = not args.no_i5 and chronology.ENABLED
    contract.LAYOUT_ENABLED = not args.no_i6  # takes effect only with I5 (briefing.i6_active)
    company_context.ENABLED = not args.no_i7  # the prompt layer takes effect only with I6 (briefing.i7_active)
    global ONLY, VARIANT, DOTENV, LEDGER, USE
    USE = SCENARIOS + EXTRA_DEV if args.all_dev else SCENARIOS
    ONLY = tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
    VARIANT = args.variant
    DOTENV = args.dotenv
    if args.ledger:
        LEDGER = args.ledger
    if any(s not in USE for s in ONLY):
        raise SystemExit(f"--scenarios must be among {', '.join(USE)}")
    apply_variant(args.variant)
    compiled = h.compile_split("dev")  # development split only; the held-out split is never compiled here
    if run.names_in_production(compiled):
        raise h.IsolationError("benchmark names found in production code")
    CP0.mkdir(parents=True, exist_ok=True)
    from deal_prep import evidence
    evidence.PROFILE_IN_MODEL_INPUT = not args.no_profile  # this process only
    return dry_run(compiled) if args.dry_run else live(compiled, run_cap=args.run_cap, tag=args.tag,
                                                       daily_cap=args.daily_cap)


if __name__ == "__main__":
    sys.exit(main())
