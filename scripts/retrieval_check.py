"""Build the DMS index offline and compare retrieval with pre-written expectations.

Usage: python scripts/retrieval_check.py
Writes ranked results to runs/gate01_retrieval_<timestamp>.json (gitignored).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_prep import config  # noqa: E402
from deal_prep.chunking import chunk_corpus  # noqa: E402
from deal_prep.corpus import load_documents  # noqa: E402
from deal_prep.evaluation import score  # noqa: E402
from deal_prep.index import build_index, query  # noqa: E402

EXPECTATIONS = ROOT / "tests" / "fixtures" / "retrieval_expectations.json"


def main() -> int:
    spec = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    chunks = chunk_corpus(load_documents())
    build_index(chunks)
    print(f"Indexed {len(chunks)} chunks into {config.COLLECTION_NAME} at {config.CHROMA_DIR}")

    rows = [score(q, query(q["question"], k=spec["k"])) for q in spec["questions"]]

    print(f"\n{'ID':<4} {'expected chunk':<16} {'doc hit':<8} {'doc rank':<9} {'passage hit':<12} passage rank   top-5 observed")
    for r in rows:
        top = ", ".join(o["chunk_id"] for o in r["observed"])
        print(f"{r['id']:<4} {r['expected_chunk_id']:<16} {str(r['document_hit']):<8} {str(r['document_rank']):<9} "
              f"{str(r['passage_hit']):<12} {str(r['passage_rank']):<14} {top}")
    doc_hits = sum(r["document_hit"] for r in rows)
    passage_hits = sum(r["passage_hit"] for r in rows)
    print(f"\nDocument-level hits@{spec['k']}: {doc_hits}/{len(rows)}   Passage-level hits@{spec['k']}: {passage_hits}/{len(rows)}")

    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"gate01_retrieval_{ts}.json"
    out.write_text(json.dumps({"run_at_utc": ts, "expectations_version": spec["version"],
                               "embedding_model": config.EMBEDDING_MODEL, "k": spec["k"],
                               "results": rows}, indent=2), encoding="utf-8")
    print(f"Saved: {out.relative_to(ROOT)}")
    return 0 if passage_hits == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
