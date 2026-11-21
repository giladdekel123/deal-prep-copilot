"""Phase 4.5: run and score the fictional benchmark (FICTIONAL TEST DATA), offline template drafting, in isolation.

Usage: python scripts/benchmark_run.py [--split dev] [--news both|news_fixture|news_off] [--repeat 2]
  - Development split by default. The held-out split runs only after it is frozen (heldout/FROZEN.sha256 matches),
    at most 3 times in total, and only if no held-out company name or domain appears in src/ or app/.
  - Each scenario runs in its own fresh folder under runs/benchmark_v1/<run>/ (index, history database, rendered
    corpus). Outbound connections are blocked; no .env or API keys are read; the clock is fixed.
  - news_fixture replays fixture news; news_off switches news off exactly as the offline demo does. The two modes
    are reported in separate tables and never combined.
  - --repeat N runs every scenario N times; the offline layer must give identical results each time.
  - Protected local data (chroma_db/, runs/history.sqlite, the walkthrough history, data/, src/, app/) is
    fingerprinted before and after; any change is reported as an isolation failure.
Writes runs/benchmark_v1/<run>/records.json, score.json and summary.md; appends to runs/benchmark_v1/invocations.jsonl.
Held-out split (aggregate-only, owner decision at I0-c): every detailed output (records, per-scenario scores, failure
and vacuous-pass details, rendered corpus, console output of the run) goes only to the gitignored owner folder
runs/benchmark_v1/heldout_private/<run>/. The terminal and runs/benchmark_v1/<run>_heldout/ receive aggregate counts
only (passed / applicable, vacuous counts, intervals, rule coverage and limitations).
These are offline template results. They say nothing about the live AI drafter.
"""
import argparse
import contextlib
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_harness as h  # noqa: E402  (sets the offline environment before deal_prep is imported)
import benchmark_score as s  # noqa: E402

WALKTHROUGH = h.ROOT / "runs" / "demo_walkthrough_20261108"
PROTECTED = [h.ROOT / "chroma_db", h.ROOT / "runs" / "history.sqlite",
             WALKTHROUGH, h.ROOT / "data", h.ROOT / "src", h.ROOT / "app"]


def transient_log(p: Path) -> bool:
    """Owner decision (I2): only the walkthrough app's own *.log files, directly in the walkthrough folder, are
    transient (a running app appends to them). Everything else, including the walkthrough history database and
    index, stays protected."""
    return p.suffix == ".log" and p.parent == WALKTHROUGH
HELDOUT_RUN_LIMIT = 3
INVOCATIONS = h.RUNS / "invocations.jsonl"
PUBLIC = h.RUNS  # aggregate held-out outputs go to PUBLIC/<run>_heldout
PRIVATE = h.RUNS / "heldout_private"  # detailed held-out outputs: owner only, never printed
AGGREGATE_KEYS = ("description", "coverage", "passed", "applicable", "vacuous_passes", "substantive_passes",
                  "related", "wilson95", "note")


def aggregate_only(aggs: dict) -> dict:
    """Metric counts without failure or vacuous-pass details (those name evidence and reveal held-out values)."""
    return {mode: {m: {k: a[k] for k in AGGREGATE_KEYS} for m, a in agg.items()} for mode, agg in aggs.items()}


@contextlib.contextmanager
def private_console(log_path: Path):
    """Send everything written to stdout/stderr (Python and native) to a private log file while inside."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.flush(), sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with open(log_path, "a", encoding="utf-8") as log:
        os.dup2(log.fileno(), 1), os.dup2(log.fileno(), 2)
        old = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            yield
        finally:
            log.flush()
            sys.stdout, sys.stderr = old
            os.dup2(saved[0], 1), os.dup2(saved[1], 2)
            os.close(saved[0]), os.close(saved[1])


def fingerprint(paths=PROTECTED) -> str:
    digest = hashlib.sha256()
    for root in paths:
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []
        for p in files:
            if "__pycache__" in p.parts or transient_log(p):
                continue
            st = p.stat()
            digest.update(f"{p.relative_to(h.ROOT)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def names_in_production(compiled: list[dict]) -> list[str]:
    """Benchmark company names, aliases or domains that appear in production code (must be none)."""
    needles = {n.casefold() for c in compiled for o in c["registry"] for n in [o["name"], *o["aliases"], o["official_domain"]]}
    hits = []
    for folder in ("src", "app"):
        for p in (h.ROOT / folder).rglob("*.py"):
            text = p.read_text(encoding="utf-8").casefold()
            hits += [f"{p.relative_to(h.ROOT)}: {n}" for n in needles if n in text]
    return hits


def heldout_runs_so_far() -> int:
    if not INVOCATIONS.exists():
        return 0
    return sum(json.loads(l).get("split") == "heldout" for l in INVOCATIONS.read_text(encoding="utf-8").splitlines() if l)


def table(agg: dict) -> list[str]:
    lines = ["| Metric | Description | Rule coverage | Passed / applicable | of which vacuous | 95% interval | Read with |",
             "|---|---|---|---|---|---|---|"]
    for m, a in agg.items():
        ci = f"{a['wilson95'][0]:.2f}–{a['wilson95'][1]:.2f}" if a["wilson95"] else "n/a"
        lines.append(f"| {m} | {a['description']} | {a['coverage']} | {a['passed']} / {a['applicable']} | "
                     f"{a['vacuous_passes']} | {ci} | {a['related']} |")
    return lines


def summary_md(run_id, split, n_scen, repeat, aggs: dict, deterministic, isolation, blocked, detailed=True) -> str:
    lines = [f"# Benchmark run {run_id} ({split} split, OFFLINE TEMPLATE layer) — FICTIONAL TEST DATA", "",
             f"**{h.LABEL}**", "",
             f"Scenarios: {n_scen}; repeats: {repeat}; clock {h.CLOCK.isoformat()}.",
             "These are offline template results. They are not evidence about the live AI drafter, and a sample of "
             "this size is not evidence of general quality.", "",
             f"- Offline determinism (identical results across repeats): {'yes' if deterministic else 'NO'}",
             f"- Protected local data unchanged: {'yes' if isolation else 'NO'}",
             f"- Outbound connection attempts: {len(blocked)}", "",
             "Rule coverage: **full** = the rule decides the property exactly, given the expected outcomes; "
             "**approximation** = a proxy that can miss cases; **partial** = checks one part only, so a full count "
             "is NOT a 100% result for the property. No metric here measures overall factual accuracy. "
             "Factual support is established only by the separate manual claim-support audit (plan §6.1 F).", "",
             "A **vacuous** pass is one that succeeded only because the evidence or capability it tests was absent "
             "(nothing could have gone wrong). Vacuous passes are not evidence of a capability; read them with the "
             "related metric. Metrics with 0 applicable units were not measured in that mode.", ""]
    for mode, agg in aggs.items():
        lines += [f"## Mode: {mode}", ""] + table(agg) + [""]
    if not detailed:
        lines += ["## Failure details", "",
                  "Held-out split: aggregate counts only. Failure and vacuous-pass details are kept for the owner in "
                  "the gitignored folder runs/benchmark_v1/heldout_private/ and are not shown here.", ""]
    for mode, agg in (aggs.items() if detailed else []):
        lines += [f"## Failures ({mode})", ""]
        lines += [f"- **{m}** {f}" for m, a in agg.items() for f in a["failures"]] or ["- none"]
        lines += ["", f"## Vacuous passes, not capability ({mode})", ""]
        lines += [f"- **{m}** {v}" for m, a in agg.items() for v in a["vacuous"]] or ["- none"]
        lines.append("")
    any_agg = next(iter(aggs.values()))
    lines += ["## Scorer limitations", ""] + [f"- {m} ({a['coverage']}): {a['note']}" for m, a in any_agg.items() if a["note"]]
    lines += ["", "## Not measured by this benchmark", ""] + [f"- {x}" for x in s.NOT_MEASURED]
    lines += ["", "## Known benchmark limitation (Option A)", "",
              "- Inside the isolated benchmark registry the fictional companies carry reality 'real' so that the "
              "unchanged production pipeline treats them as registered companies. Production-generated labels in "
              "the run records therefore read '(real, customer)' or 'relationship with a real company'. That wording "
              "is inaccurate here: every benchmark entity is fictional. The app never loads this registry.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "heldout"])
    ap.add_argument("--news", default="both", choices=["both", *h.NEWS_MODES])
    ap.add_argument("--repeat", type=int, default=2)
    args = ap.parse_args(argv)
    if args.split == "heldout":
        h.assert_heldout_frozen()
        if heldout_runs_so_far() >= HELDOUT_RUN_LIMIT:
            raise PermissionError(f"the held-out split has already been run {HELDOUT_RUN_LIMIT} times")
    modes = list(h.NEWS_MODES) if args.news == "both" else [args.news]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(INVOCATIONS, "a", encoding="utf-8") as f:  # logged before running, so a failed held-out run still counts
        f.write(json.dumps({"run_id": run_id, "split": args.split, "news": modes, "repeat": args.repeat}) + "\n")
    if args.split == "dev":
        return execute(args, modes, run_id, h.RUNS / f"{run_id}_dev", detailed_out=True)
    private = PRIVATE / f"{run_id}_heldout"
    log = private / "run.log"
    try:
        with private_console(log):
            result = execute(args, modes, run_id, private, detailed_out=False)
    except BaseException:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise RuntimeError(f"the held-out run failed; the details are only in the owner's private log "
                           f"{log.relative_to(h.ROOT)}") from None
    public = PUBLIC / f"{run_id}_heldout"
    public.mkdir(parents=True, exist_ok=True)
    (public / "score_aggregate.json").write_text(json.dumps(result["aggregate_score"], indent=1, ensure_ascii=False),
                                                 encoding="utf-8")
    (public / "summary.md").write_text(result["aggregate_summary"], encoding="utf-8")
    print(result["aggregate_summary"])
    return result["code"]


def execute(args, modes, run_id, out: Path, detailed_out: bool):
    compiled = h.compile_split(args.split, allow_heldout=args.split == "heldout")
    leaked = names_in_production(compiled)
    if leaked:
        raise h.IsolationError("benchmark names found in production code: " + "; ".join(leaked))
    scenarios = [sc for c in compiled for sc in c["scenarios"]]
    before = fingerprint()
    records, canon = [], {}
    for r in range(args.repeat):
        for mode in modes:
            for sc in scenarios:
                rec = h.run_scenario(sc, compiled, out / f"rep{r}" / mode / sc["id"], mode)
                canon.setdefault((sc["id"], mode), set()).add(h.canonical(rec))
                if r == 0:
                    records.append(rec)
    after = fingerprint()
    deterministic = all(len(v) == 1 for v in canon.values())
    blocked = [b for rec in records for b in rec["blocked_connections"]]
    per = {mode: [s.score_scenario(rec) for rec in records if rec["news_mode"] == mode] for mode in modes}
    aggs = {mode: s.aggregate(p) for mode, p in per.items()}
    score = {"label": h.LABEL, "run_id": run_id, "split": args.split, "layer": "offline_template",
             "scorer_version": s.SCORER_VERSION, "modes": modes,
             "scenarios": len(scenarios), "repeat": args.repeat, "deterministic": deterministic,
             "protected_unchanged": before == after, "blocked_connections": blocked, "metrics": aggs,
             "per_scenario": {f"{rec['scenario']}|{rec['news_mode']}": sc for mode in modes
                              for rec, sc in zip([x for x in records if x["news_mode"] == mode], per[mode])}}
    (out / "records.json").write_text(json.dumps({"label": h.LABEL, "records": records}, indent=1, ensure_ascii=False,
                                                 default=str), encoding="utf-8")
    (out / "score.json").write_text(json.dumps(score, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "summary.md").write_text(summary_md(run_id, args.split, len(scenarios), args.repeat, aggs, deterministic,
                                               before == after, blocked), encoding="utf-8")
    code = 0 if (deterministic and before == after and not blocked) else 1
    if detailed_out:
        print((out / "summary.md").read_text(encoding="utf-8"))
        return code
    agg_score = {k: v for k, v in score.items() if k not in ("metrics", "per_scenario", "blocked_connections")}
    agg_score.update(metrics=aggregate_only(aggs), blocked_connections=len(blocked), detail="aggregate only")
    return {"code": code, "aggregate_score": agg_score,
            "aggregate_summary": summary_md(run_id, args.split, len(scenarios), args.repeat, aggregate_only(aggs),
                                            deterministic, before == after, blocked, detailed=False)}


if __name__ == "__main__":
    sys.exit(main())
