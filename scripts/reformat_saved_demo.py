"""Re-compose the saved SIMULATED demonstration with the current shared offline logic (offline; no research).

Usage: python scripts/reformat_saved_demo.py

The briefing items are rebuilt by the same TemplateDrafter used for every offline briefing, run over the
evidence already stored in the saved record (nothing is searched, added or edited). The disclosures are
rebuilt by the shared disclosure rules from the record's stored gaps and research status. Unchanged: the
creation date, run ID, identity, evidence, labels, trace and usage. Every citation must point to evidence
already in the record, with the origin its claim type requires; otherwise nothing is written.
A dated note records that the text was re-composed and that the briefing was not newly researched.
Running it again gives the same file.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_prep import demo  # noqa: E402
from deal_prep.app_service import SAVED_DEMO_PATH, load_saved_demo  # noqa: E402
from deal_prep.authority import CLAIM_ORIGINS  # noqa: E402
from deal_prep.briefing import _parse  # noqa: E402
from deal_prep.disclosures import required_disclosures  # noqa: E402

NOTE = ("Re-composed on 21 November 2026 by the current offline template from the same stored evidence; "
        "not newly researched. Public portfolio version: the public-source statements are project-written summaries, "
        "not quotations.")
NEWS_GAP_PREFIX = "News was not searched: "


def _stored_news_gap(saved: dict) -> str:
    """The stored news gap: the gap disclosure, or (after a previous run) the reason kept in the trace."""
    for d in saved["disclosures"]:
        if d["id"].startswith("gap:") and d["text"].startswith(NEWS_GAP_PREFIX):
            return d["text"]
    skipped = next(t["outcome"] for t in saved["trace"] if t.get("stage") == "external_news")
    return f"{NEWS_GAP_PREFIX}{skipped.removeprefix('skipped: ')}."


def recompose(saved: dict) -> dict:
    news_gap = _stored_news_gap(saved)
    other_gaps = [d["text"] for d in saved["disclosures"] if d["id"].startswith("gap:") and d["text"] != news_gap]
    bundle = {"created_at": saved["created_at"], "status": "partial_internal_only", "internal": {},
              "gaps": other_gaps + [news_gap], "external": {"status": "disabled", "message": news_gap}}
    disclosures = required_disclosures(bundle)
    payload = {"company": saved["identity"]["name"], "meeting_purpose": saved["purpose"],
               "research_status": "partial_internal_only", "gaps": bundle["gaps"], "news_status": "disabled",
               "required_disclosures": [{"id": d["id"], "text": d["text"]} for d in disclosures],
               "evidence": list(saved["evidence"].values())}
    drafted = _parse(demo.TemplateDrafter()([{"role": "system", "content": ""},
                                             {"role": "user", "content": json.dumps(payload)}])).model_dump()
    for section, items in drafted["sections"].items():
        for item in items:
            for eid in item["evidence_ids"]:
                ev = saved["evidence"].get(eid)
                if ev is None:
                    raise SystemExit(f"{section}: cites {eid}, which is not in the saved evidence; nothing written")
                if item["kind"] == "fact" and ev["info_origin"] != CLAIM_ORIGINS[item["claim_type"]]:
                    raise SystemExit(f"{section}: {item['claim_type']} cites {eid} ({ev['info_origin']}); nothing written")
    return {**saved, "briefing": drafted["sections"], "disclosures": disclosures, "reformatted_note": NOTE,
            "generation_label": f"{demo.GENERATION_LABEL} {NOTE}"}


def main() -> int:
    saved = recompose(load_saved_demo())
    SAVED_DEMO_PATH.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Re-composed {SAVED_DEMO_PATH.relative_to(ROOT)} (created {saved['created_at']}, not re-researched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
