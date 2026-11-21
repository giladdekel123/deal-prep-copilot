"""Prompt 07 step 5: offline demo rehearsal and saved-versus-live label audit.

Usage: python scripts/demo_rehearsal.py
Rehearses, in offline demo mode with all non-loopback network connections blocked:
  - the saved SIMULATED demonstration (Shikun & Binui),
  - the three curated companies (Shikun & Binui, Ashtrom Group, Arup with arup.com),
  - an arbitrary company outside the registry (Teva Pharmaceutical),
  - the ambiguous name "Arup" without a domain,
  - a repeated request (must reuse the cached result, never re-research).
Each scenario is checked deterministically: status, research date, mode/generation labels, origin labels,
gaps, one-page EN and HE PDFs. A temporary index and history database are used, so local data is untouched.
No API keys are read and nothing is sent anywhere. Writes runs/demo_rehearsal_<timestamp>.json.
Exit code 1 if any check fails.
"""
import json
import os
import socket
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for k, v in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "ANONYMIZED_TELEMETRY": "False",
             "DEAL_PREP_NO_DOTENV": "1"}.items():
    os.environ[k] = v
for k in ("OPENAI_API_KEY", "TAVILY_API_KEY"):
    os.environ.pop(k, None)

blocked = []
_connect = socket.socket.connect


def guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ("127.0.0.1", "::1", "localhost"):
        blocked.append(str(address))
        raise OSError(f"network blocked during offline rehearsal: {address}")
    return _connect(self, address)


socket.socket.connect = guarded_connect

from deal_prep.app_service import SAVED_DEMO_PATH, SAVED_MODE_LABEL, BriefingService, available_modes  # noqa: E402
from deal_prep.demo import GENERATION_LABEL, PREFIXES  # noqa: E402
from deal_prep.pdf_export import MAX_PAGES, MIN_FONT, build_pdf  # noqa: E402
from deal_prep.pipeline import STATUS_TEXT  # noqa: E402

FAILURE_WORDING = ("failed", "could not be completed", "unavailable")  # never used for a deliberately skipped search

SCENARIOS = [  # (label, company, domain, purpose, expected statuses)
    ("Curated: Shikun & Binui (proposal sent, follow-up)", "Shikun & Binui", None, "follow_up", {"partial_briefing"}),
    ("Curated: Ashtrom Group (new lead)", "Ashtrom Group", None, "introduction", {"partial_briefing"}),
    ("Curated: Arup (negotiation, public conflict)", "Arup", "arup.com", "negotiation", {"partial_briefing"}),
    ("Arbitrary company outside the registry", "Teva Pharmaceutical", None, "general", {"no_briefing"}),
    ("Ambiguous name without domain", "Arup", None, "general", {"clarification_required"}),
]


def pdf_pages(result: dict) -> dict:
    from io import BytesIO

    from pypdf import PdfReader
    return {lang: len(PdfReader(BytesIO(build_pdf(result, result.get("generation_label", ""), lang)[0])).pages)
            for lang in ("en", "he")}


def section_counts(result: dict) -> dict:
    return {k: len(v) for k, v in (result.get("briefing") or {}).items()}


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checks, scenarios = [], []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # Chroma keeps its index files open until the process exits, so Windows cleanup may leave the folder behind.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = BriefingService(chroma_dir=Path(tmp) / "chroma", history_path=Path(tmp) / "history.sqlite")
        check("Only offline demo mode is offered without keys", list(available_modes()) == ["offline_demo"],
              str(list(available_modes())))

        # Saved SIMULATED demonstration
        from deal_prep.app_service import load_saved_demo
        on_disk = json.loads(SAVED_DEMO_PATH.read_text(encoding="utf-8"))
        demo = load_saved_demo()
        check("Saved demo keeps its original creation date", demo["created_at"] == on_disk["created_at"],
              demo["created_at"])
        check("Saved demo is labelled SIMULATED", demo["mode_label"] == SAVED_MODE_LABEL and "SIMULATED" in
              demo["mode_label"], demo["mode_label"])
        check("Saved demo never triggers research", service.runs == 0, f"service runs {service.runs}")
        pages = pdf_pages(demo)
        check("Saved demo PDFs are two pages (EN/HE)", pages == {"en": 2, "he": 2}, str(pages))
        scenarios.append({"scenario": "Saved SIMULATED demonstration", "status": demo["status"],
                          "created_at": demo["created_at"], "mode_label": demo["mode_label"],
                          "sections": section_counts(demo), "pdf_pages": pages})

        for label, company, domain, purpose, expected in SCENARIOS:
            started = time.monotonic()
            before = datetime.now(timezone.utc)
            result, ran = service.get(company, domain, purpose)
            elapsed = round(time.monotonic() - started, 1)
            row = {"scenario": label, "company": company, "domain": domain, "purpose": purpose,
                   "status": result["status"], "ran_now": ran, "seconds": elapsed,
                   "created_at": result["created_at"], "mode_label": result.get("mode_label"),
                   "generation_label": result.get("generation_label"), "labels": result.get("labels"),
                   "sections": section_counts(result), "message": result.get("message", ""),
                   "gaps": [d["text"] for d in result.get("disclosures", []) if d["id"].startswith("gap")]}
            check(f"{label}: status {sorted(expected)}", result["status"] in expected, result["status"])
            check(f"{label}: research date is this run", datetime.fromisoformat(result["created_at"]) >= before,
                  result["created_at"])
            if result["status"] in ("briefing_ready", "partial_briefing"):
                row["pdf_pages"] = pdf_pages(result)
                check(f"{label}: offline labels", result["mode_label"].startswith("Offline demo")
                      and result["generation_label"] == GENERATION_LABEL
                      and result["labels"]["market_intelligence"].startswith("not included"),
                      f"{result['labels']}")
                visible = [STATUS_TEXT[result["status"]], result.get("message", ""), *result["labels"].values(),
                           *(d["text"] for d in result["disclosures"])]
                wrong = [t for t in visible if any(w in t.lower() for w in FAILURE_WORDING)]
                check(f"{label}: news reported as not searched, not as a failure",
                      "not searched" in result["labels"]["market_intelligence"] and not wrong,
                      "; ".join(wrong) or result["labels"]["market_intelligence"])
                items = [i for section in result["briefing"].values() for i in section]
                prefixes = (*PREFIXES.values(), "Use the competitor battlecard: ")
                body = {i["text"]: next((i["text"][len(p):] for p in prefixes if i["text"].startswith(p)), i["text"])
                        for i in items}
                raw = [i["text"] for i in items if " | " in i["text"] or body[i["text"]][:1].islower()
                       or any(result["evidence"][e]["excerpt"].startswith("Limitations") for e in i["evidence_ids"])]
                check(f"{label}: items read as sentences (no table syntax or snapshot caveats)", not raw,
                      "; ".join(raw) or f"{len(items)} items")
                # Owner-approved change to FR-09/AT-06 (2026-11-15): one page preferred; more pages allowed so that
                # all text stays at 8 pt or larger and nothing is shortened. Since the PDF redesign (about 10 pt body text, natural
                # pagination) the saved demo is two pages, which the check above expects.
                check(f"{label}: PDFs readable (EN/HE: at most {MAX_PAGES} pages, text at least {MIN_FONT:g} pt)",
                      all(1 <= p <= MAX_PAGES for p in row["pdf_pages"].values()), str(row["pdf_pages"]))
                evidence = result["evidence"].values()
                check(f"{label}: every evidence item has an origin label",
                      all(e["provenance_label"].startswith(("PUBLIC SOURCE", "SYNTHETIC")) for e in evidence),
                      f"{len(result['evidence'])} items")
                rel = [result["evidence"][i]["info_origin"] for item in result["briefing"]["our_relationship"]
                       for i in item["evidence_ids"]]
                check(f"{label}: 'Our relationship' cites synthetic records only",
                      all(o == "synthetic_record" for o in rel), f"{len(rel)} citations")
            scenarios.append(row)

        runs_before = service.runs
        again, ran = service.get("Shikun & Binui", None, "follow_up")
        check("Repeated request reuses the saved result (no new research)", not ran and service.runs == runs_before,
              f"ran_now {ran}, runs {service.runs}")

    check("No outbound network connection was attempted", not blocked, ", ".join(blocked) or "none")
    record = {"run_at_utc": stamp, "scenarios": scenarios, "checks": checks,
              "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks)}
    out = ROOT / "runs" / f"demo_rehearsal_{stamp}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    for s in scenarios:
        print(f"{s['scenario']:<45} {s['status']:<22} {s.get('seconds', '-')!s:>5} s  sections "
              f"{sum(s['sections'].values())}  PDF {s.get('pdf_pages', '-')}")
    for c in checks:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']}  ({c['detail']})")
    print(f"\n{record['passed']} checks passed, {record['failed']} failed. Saved: {out.relative_to(ROOT)}")
    return 0 if record["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
