"""Build dms_kb_v1 offline and evaluate it against eval/cases_v1.json.

Usage: python scripts/kb_eval.py
Reports Recall@k at document and passage level (measured, no pre-set threshold), plus
pass/fail provenance, isolation and authority cases. Writes runs/kb_eval_<timestamp>.json.
Exit code 1 if any provenance or authority case fails.
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_prep import authority  # noqa: E402
from deal_prep.kb_index import (build_kb_index, load_kb_chunks, resolve_company,  # noqa: E402
                                search, to_evidence)
from deal_prep.provenance import load_registry  # noqa: E402

CASES = json.loads((ROOT / "eval" / "cases_v1.json").read_text(encoding="utf-8"))
K = CASES["k"]
seen_evidence = []


def run_search(question, **kw):
    results = search(question, k=K, **kw)
    seen_evidence.extend(results)
    return results


def retrieval_case(c):
    results = run_search(c["question"], company_id=c["company"])
    doc_rank = next((e["rank"] for e in results if e["document_id"] == c["expected_document_id"]), None)
    passage_rank = next((e["rank"] for e in results if e["document_id"] == c["expected_document_id"]
                         and all(s in e["text"] for s in c["must_contain"])), None)
    return {"id": c["id"], "format": c["format"], "expected": c["expected_document_id"],
            "doc_rank": doc_rank, "passage_rank": passage_rank,
            "top": [e["evidence_id"] for e in results]}


def provenance_case(c):
    kind = c["kind"]
    if kind == "isolation":
        bad = [e["evidence_id"] for e in run_search(c["question"], company_id=c["company"])
               if e["metadata"]["scope"] != "global"
               and c["company"] not in (e["metadata"]["customer_org_id"], e["metadata"]["subject_org_id"])]
        return not bad, f"foreign results: {bad}"
    if kind == "resolution":
        r = resolve_company(c["name"], domain=c.get("domain"))
        ok = r["status"] == c["expect_status"] and (
            r["candidates"] == c["expect_candidates"] if "expect_candidates" in c else r["org_id"] == c["expect_org_id"])
        return ok, str(r)
    if kind == "unknown_company":
        r = resolve_company(c["name"])
        results = run_search(c["question"], global_only=True)
        ok = r["status"] == c["expect_status"] and all(e["metadata"]["scope"] == "global" for e in results)
        return ok, f"{r['status']}, {len(results)} global results"
    if kind == "relationship_origin":
        tied = [e for e in run_search(c["question"], company_id=c["company"])
                if e["metadata"]["customer_org_id"] == c["company"]]
        ok = all(e["info_origin"] == "synthetic_record" and e["provenance_label"].startswith("SYNTHETIC") for e in tied)
        return ok, f"{len(tied)} customer-tied results, all synthetic={ok}"
    if kind == "origin_filter":
        results = run_search(c["question"], company_id=c["company"], origin=c["origin"])
        return bool(results) and all(e["info_origin"] == c["origin"] for e in results), f"{len(results)} results"
    if kind == "labels":
        def complete(e):
            m = e["metadata"]
            if not e["provenance_label"]:
                return False
            return e["info_origin"] != "public_source" or all(
                m[f] and str(m[f]) in e["provenance_label"] for f in ("source_url", "retrieved_at", "publication_date"))
        bad = [e["evidence_id"] for e in seen_evidence if not complete(e)]
        return not bad, f"{len(seen_evidence)} evidence objects checked; incomplete: {bad}"
    raise ValueError(kind)


def authority_cases():
    registry = load_registry()
    ev = [to_evidence(c["chunk_id"], c["text"], c["metadata"], registry) for c in load_kb_chunks()]
    doc = lambda *ids: [e for e in ev if e["document_id"] in ids]  # noqa: E731
    out = {}
    r = authority.current_list_price(ev, "Nivarque Core", "Business", date(2026, 11, 6))
    out["A1"] = (r["status"] == "resolved" and r["value"] == "34", f"{r['status']} {r['value']}")
    r = authority.current_list_price(ev, "Nivarque Core", "Business", date(2026, 6, 1))
    out["A2"] = (r["status"] == "resolved" and r["value"] == "30", f"{r['status']} {r['value']}")
    r = authority.policy_statement([e for e in doc("NVQ-PRD-001", "NVQ-POL-002") if "SCIM" in e["text"]], date(2026, 11, 6))
    out["A3"] = (r["status"] == "unresolved", r["status"])
    lp = authority.current_list_price(ev, "Nivarque Engineering Vault", "Enterprise", date(2026, 11, 6))
    offer = authority.historical_offer(ev, "arup", "Nivarque Engineering Vault")
    out["A4"] = (lp["value"] == "52" and any("NVQ-PRP-002" in i for i, _ in lp["rejected"])
                 and offer["value"]["proposed_price_usd"] == ["46"], f"list {lp['value']}, offer {offer['value']}")
    claim = [e for e in doc("NVQ-MTG-002") if "1985" in e["text"]]
    public = [e for e in doc("NVQ-PUB-005", "NVQ-PUB-007") if "trust" in e["text"].lower()]
    r = authority.real_world_fact(claim + public)
    out["A5"] = (r["status"] == "unresolved" and [i.split("#")[0] for i in r["origin_violations"]] == ["NVQ-MTG-002"],
                 f"{r['status']}, violations {r['origin_violations']}")
    r = authority.meeting_history(doc("NVQ-MTG-001", "NVQ-MTG-002"))
    out["A6"] = (r["status"] == "resolved" and {i.split("#")[0] for i, _ in r["rejected"]} == {"NVQ-MTG-002"},
                 f"{r['status']}, rejected {[i for i, _ in r['rejected']]}")
    return out


def main() -> int:
    collection = build_kb_index()
    print(f"Built dms_kb_v1 with {collection.count()} chunks")

    rows = [retrieval_case(c) for c in CASES["retrieval"]]
    print(f"\nRetrieval (k={K})\n{'ID':<4} {'fmt':<5} {'expected':<16} {'doc rank':<9} {'passage rank':<13} top-{K}")
    for r in rows:
        print(f"{r['id']:<4} {r['format']:<5} {r['expected']:<16} {str(r['doc_rank']):<9} "
              f"{str(r['passage_rank']):<13} {', '.join(r['top'])}")
    n = len(rows)
    doc_hits = sum(r["doc_rank"] is not None for r in rows)
    passage_hits = sum(r["passage_rank"] is not None for r in rows)
    print(f"Document-level Recall@{K}: {doc_hits}/{n}   Passage-level Recall@{K}: {passage_hits}/{n}")

    prov = {c["id"]: provenance_case(c) for c in CASES["provenance"] if c["kind"] != "labels"}
    prov.update({c["id"]: provenance_case(c) for c in CASES["provenance"] if c["kind"] == "labels"})
    auth = authority_cases()
    print("\nProvenance / isolation")
    for cid, (ok, detail) in prov.items():
        print(f"  {cid}: {'PASS' if ok else 'FAIL'}  {detail}")
    print("Authority")
    for cid, (ok, detail) in auth.items():
        print(f"  {cid}: {'PASS' if ok else 'FAIL'}  {detail}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "runs" / f"kb_eval_{ts}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"run_at_utc": ts, "cases_version": CASES["version"], "k": K,
                               "retrieval": rows, "doc_recall": f"{doc_hits}/{n}", "passage_recall": f"{passage_hits}/{n}",
                               "provenance": {k: {"pass": v[0], "detail": v[1]} for k, v in prov.items()},
                               "authority": {k: {"pass": v[0], "detail": v[1]} for k, v in auth.items()}},
                              indent=2), encoding="utf-8")
    print(f"\nSaved: {out.relative_to(ROOT)}")
    return 0 if all(v[0] for v in [*prov.values(), *auth.values()]) else 1


if __name__ == "__main__":
    sys.exit(main())
