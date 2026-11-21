"""Phase 4.5: re-score saved DEVELOPMENT run records with a chosen scorer version (no rerun, no API call).

Usage: python scripts/benchmark_rescore.py runs/benchmark_v1/<run>/records.json [--version 1.1]
Writes <run>/rescored_v<version>.json next to the records and prints the counts per metric and news mode.
The saved records are never modified, so the original scores stay as recorded. Held-out records are refused.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_harness as h  # noqa: E402
import benchmark_score as s  # noqa: E402


def rescore(records_path: Path, version: str) -> dict:
    p = records_path.resolve()
    if "heldout" in p.as_posix().casefold() or (h.RUNS / "heldout_private").resolve() in p.parents:
        raise PermissionError("held-out records are never re-scored by development tools")
    records = json.loads(p.read_text(encoding="utf-8"))["records"]
    if not all(str(r.get("scenario", "")).startswith("DEV-") for r in records):
        raise PermissionError("only development scenarios (DEV-*) are re-scored by development tools")
    scored = [r for r in records if not r.get("error")]
    modes = sorted({r["news_mode"] for r in scored})
    metrics = {m: s.aggregate([s.score_scenario(r, version=version) for r in scored if r["news_mode"] == m])
               for m in modes}
    return {"label": h.LABEL, "source": p.relative_to(h.ROOT).as_posix(), "scorer_version": version,
            "scorer_changes": s.SCORER_CHANGES.get(version, []), "metrics": metrics}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("records")
    ap.add_argument("--version", default=s.SCORER_VERSION)
    a = ap.parse_args(argv)
    out = rescore(Path(a.records), a.version)
    target = Path(a.records).resolve().parent / f"rescored_v{a.version}.json"
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for mode, agg in out["metrics"].items():
        print(f"[{mode}] " + "  ".join(f"{m} {x['passed']}/{x['applicable']}" for m, x in agg.items()))
    print(f"Saved: {target.relative_to(h.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
