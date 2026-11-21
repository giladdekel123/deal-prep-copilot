"""Phase 4.5 I0-b: the owner's held-out review tool (FICTIONAL TEST DATA). It never prints a value.

Usage (run it in your own terminal):
  python scripts/benchmark_heldout.py status        how many held-out values differ from the draft, per company
  python scripts/benchmark_heldout.py check         validate every form and check the expected outcomes against the
                                                    rendered evidence; prints only OK or problems by value NAME
  python scripts/benchmark_heldout.py review <n>    writes a plain-English page for company n (1-6) to
                                                    runs/benchmark_v1/heldout_review/ and prints only its path
  python scripts/benchmark_heldout.py freeze        (checkpoint A1, owner's decision only) records SHA-256 hashes
                                                    of every held-out file in eval/benchmark_v1/heldout/FROZEN.sha256
Forms: eval/benchmark_v1/heldout/forms/<code>.txt (plain text, one value per line). The first run of any command
creates missing forms from the draft values; existing forms are never overwritten.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_harness as h  # noqa: E402
import benchmark_run as run  # noqa: E402
import benchmark_spec as spec  # noqa: E402

BASE = h.BENCH / "heldout"
FORMS = BASE / "forms"
REVIEW = h.RUNS / "heldout_review"


def specs() -> list[dict]:
    return spec.load_specs(BASE / "companies")


def ensure_forms() -> None:
    FORMS.mkdir(exist_ok=True)
    all_specs = specs()
    for i, s in enumerate(all_specs, 1):
        form = FORMS / f"{s['code']}.txt"
        if not form.exists():
            form.write_text(spec.write_form(s, i, len(all_specs)), encoding="utf-8", newline="\n")


def values_of(s: dict) -> dict:
    return spec.parse_form((FORMS / f"{s['code']}.txt").read_text(encoding="utf-8"))


def status() -> int:
    for i, s in enumerate(specs(), 1):
        v, d = values_of(s), spec.defaults(s)
        changed = sum(v.get(k) != d[k] for k in d)
        print(f"Company {i} ({s['code']}): {changed} of {len(d)} values changed from the draft")
    return 0


def check() -> int:
    """Validate forms; render each company; resolve every expected reference; check open-item phrases."""
    from deal_prep.history_index import meeting_text
    from deal_prep.kb_index import load_kb_chunks
    problems = {}
    compiled = []
    for i, s in enumerate(specs(), 1):
        p = spec.consistency_problems(s, values_of(s))
        if p:
            problems[i] = p
        else:
            compiled.append((i, s, spec.compile_company(s, values_of(s), h.CLOCK)))
    work = h.RUNS / "heldout_check"
    try:
        with h.benchmark_environment([c for _, _, c in compiled], work):
            chunks = {c["chunk_id"]: c["text"] for c in load_kb_chunks()}  # runs the production validator too
        for i, s, c in compiled:
            full = dict(chunks)
            news_ids = {}
            for it in c["news"]:
                full[h.news_id(it["url"])] = it["content"]
                news_ids[f"NEWS:{it['key']}"] = h.news_id(it["url"])
            for (sid, mode), exp in c["expected"].items():
                tokens, p = h.resolve_refs(h.expected_refs(exp), chunks)
                tokens.update(news_ids)
                for m in c["seed"]:  # the approved meeting text, rendered exactly as production indexes it
                    if m.get("approve"):
                        tasks = [{"description": t["description"], "status": t["final_status"],
                                  "due_date": t["due_date"], "due_raw": None} for t in m["tasks"]]
                        tokens[f"HIST:{m['key']}"] = f"HIST:{m['key']}"
                        full[f"HIST:{m['key']}"] = meeting_text({"meeting_date": m["meeting_date"],
                                                                 "approved": m["approved"]}, tasks)
                p += h.verify_expected(exp, tokens, full)
                if p:
                    problems.setdefault(i, []).extend(f"{sid} ({mode}): {x}" for x in p)
        leaked = run.names_in_production([c for _, _, c in compiled])
        if leaked:
            problems.setdefault(0, []).append(f"{len(leaked)} held-out name(s) or domain(s) found in src/ or app/")
    except Exception as e:  # noqa: BLE001 - report without values
        problems.setdefault(0, []).append(f"rendering failed: {type(e).__name__}")
    finally:
        shutil.rmtree(work, ignore_errors=True)  # the rendered held-out corpus is not kept on disk
    for i in range(len(specs()) + 1):
        if i in problems:
            print(f"Company {i}: PROBLEMS" if i else "General: PROBLEMS")
            for x in problems[i]:
                print(f"  - {x}")
        elif i:
            print(f"Company {i}: OK")
    return 1 if problems else 0


def review(n: int) -> int:
    s = specs()[n - 1]
    v = values_of(s)
    p = spec.consistency_problems(s, v)
    if p:
        print(f"Company {n}: fix the form first (run 'check').")
        return 1
    c = spec.compile_company(s, v, h.CLOCK)
    REVIEW.mkdir(parents=True, exist_ok=True)
    lines = [f"# Held-out company {n}: {s['name']} ({s['industry']}) — FICTIONAL TEST DATA", "",
             "Private review page for the owner. It shows your current values and what the benchmark will expect "
             "because of them. Do not paste it into the chat.", "", "## Your values", ""]
    lines += [f"- **{k}** = {v[k]} — {s['values'][k]['explain']}" for k in s["values"]]
    lines += ["", "## What the benchmark will expect (derived automatically)", ""]
    for (sid, mode), exp in c["expected"].items():
        sc = next(x for x in c["scenarios"] if x["id"] == sid)
        t = exp["temporal"]
        lines += [f"### {sid} — {sc['purpose'].replace('_', ' ')} — {mode.replace('_', ' ')}", "",
                  f"- Genuine contradictions to disclose: {len(t['contradictions'])}; compatible pairs not to call "
                  f"contradictions: {len(t['compatible_pairs'])}",
                  f"- Open items that must appear: " + ("; ".join(
                      f"{o['key']} ({' or '.join(o['phrases_any'])})" for o in exp['required_open_items']) or "none"),
                  f"- Products that may be recommended: {', '.join(exp['allowed_products']) or 'none'}",
                  f"- Required disclosures: {', '.join(d['contains'] for d in exp['required_disclosures']) or 'none'}",
                  ""]
    lines += ["## Sources (as rendered)", ""]
    for d in c["documents"]:
        lines += [f"### {d['manifest']['title']}", "", "```", d["text"].strip(), "```", ""]
    lines += ["## News items", ""] + [f"- ({it['when']}, {it['role']}) {it['title']}: {it['content']}" for it in c["news"]]
    page = REVIEW / f"company_{n}.md"
    page.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {page}")
    return 0


def freeze() -> int:
    if check() != 0:
        print("Not frozen: fix the problems above first.")
        return 1
    lines = ["# FROZEN held-out set (Phase 4.5 checkpoint A1). FICTIONAL TEST DATA. Do not edit held-out files.",
             *h.heldout_digest_lines()]
    h.FROZEN.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Frozen: {len(lines) - 1} files recorded in {h.FROZEN.relative_to(h.ROOT)}")
    return 0


def main(argv) -> int:
    ensure_forms()
    if not argv or argv[0] not in ("status", "check", "review", "freeze"):
        print(__doc__)
        return 2
    if argv[0] == "review":
        return review(int(argv[1]))
    return {"status": status, "check": check, "freeze": freeze}[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
