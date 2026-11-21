"""Knowledge-base v1 indexing and company-scoped retrieval (spec v1.2 §6B, D11).

One Chroma collection, dms_kb_v1. Every document passes the provenance validator and every
chunk passes a metadata check BEFORE anything is written, so invalid provenance blocks the
whole build. Results are labelled evidence objects. Labels live in metadata, not in the
embedded text. Embedding reuses the offline Prompt 01 model loader.

Retrieval is hybrid: the vector ranking and a BM25 keyword ranking over the same in-scope
chunks are combined with reciprocal rank fusion (RRF). On the 11 Gate 2B cases this lifted
document-level Recall@5 from 10/11 to 11/11; see docs/reports/GATE_02B_REPORT.md.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

from deal_prep import config
from deal_prep.corpus import resolve_document_path
from deal_prep.index import _client, embed
from deal_prep.kb_extract import extract, is_banner
from deal_prep.provenance import (CREATION_METHODS, KB_DIR, ProvenanceError, assert_valid,
                                  load_registry)

KB_COLLECTION = "dms_kb_v1"
KB_MANIFEST = KB_DIR / "manifest.json"
ROLES = ("vendor", "customer", "competitor", "subject")
SCALAR_FIELDS = (
    "document_id", "title", "file_path", "file_type", "doc_type", "info_origin", "creation_method",
    "document_version", "issued_at", "effective_from", "effective_to", "approval_status",
    "supersedes", "superseded_by", "scope", "language", "conflict_group", "fixture_tag",
    "source_url", "publisher", "publication_date", "retrieved_at", "verification_status",
)
REQUIRED_META = ("document_id", "info_origin", "creation_method", "scope", "organizations_json",
                 "provenance_label")
PUBLIC_META = ("source_url", "publisher", "publication_date", "retrieved_at", "verification_status")


def load_manifest(path: Path = KB_MANIFEST) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def provenance_label(doc: dict, registry: dict) -> str:
    if doc["info_origin"] == "public_source":
        return (f"PUBLIC SOURCE · {doc['publisher']} · {doc['source_url']} · published "
                f"{doc['publication_date']} · retrieved {doc['retrieved_at']} · "
                f"verification {doc['verification_status']}")
    orgs = ", ".join(f"{registry[o['org_id']]['name']} ({registry[o['org_id']]['reality']}, {o['role']})"
                     for o in doc["organizations"])
    return f"SYNTHETIC — not a real business fact · {orgs}"


def doc_metadata(doc: dict, registry: dict) -> dict:
    orgs = doc["organizations"]
    meta = {f: ("" if doc.get(f) is None else doc[f]) for f in SCALAR_FIELDS}
    for role in ROLES:
        meta[f"{role}_org_id"] = next((o["org_id"] for o in orgs if o["role"] == role), "")
    real = [o["org_id"] for o in orgs if registry[o["org_id"]]["reality"] == "real"]
    meta["real_org_ids"] = "|".join(real)
    meta["involves_real_org"] = bool(real)
    meta["synthetic_relationship"] = bool(doc.get("synthetic_relationship", False))
    meta["synthetic_categories"] = "|".join(doc.get("synthetic_categories", []))
    meta["organizations_json"] = json.dumps(orgs)
    meta["provenance_label"] = provenance_label(doc, registry)
    return meta


def check_chunk_metadata(meta: dict) -> None:
    """Insert-time guard: refuse a chunk whose provenance metadata is incomplete."""
    missing = [k for k in REQUIRED_META if meta.get(k) in (None, "")]
    if meta.get("info_origin") not in CREATION_METHODS:
        missing.append("info_origin (invalid)")
    if meta.get("info_origin") == "public_source":
        missing += [k for k in PUBLIC_META if meta.get(k) in (None, "")]
    if missing:
        raise ProvenanceError(f"{meta.get('chunk_id', '?')}: incomplete provenance metadata: {missing}")


class DocumentReadError(ValueError):
    """A corpus document could not be read (corrupted or unsupported file); names the document."""


def load_kb_chunks(manifest: list[dict] | None = None, registry: dict | None = None) -> list[dict]:
    """Validate every document, then chunk it. Raises ProvenanceError on the first invalid document,
    and DocumentReadError (naming the document) on the first file that cannot be read."""
    manifest = load_manifest() if manifest is None else manifest
    registry = load_registry() if registry is None else registry
    chunks = []
    for doc in manifest:
        path = resolve_document_path(doc, corpus_dir=KB_DIR)
        try:
            full_text, blocks = extract(path)
        except Exception as e:
            raise DocumentReadError(f"{doc['document_id']} ({doc['file_path']}) could not be read: "
                                    f"{type(e).__name__}: {e}") from e
        assert_valid(doc, full_text, registry)
        meta = doc_metadata(doc, registry)
        n = 0
        for b in blocks:
            if is_banner(b["text"]):
                continue
            chunk_id = f"{doc['document_id']}#{n}"
            n += 1
            prefix = b["section"] if b["section"] and not b["text"].startswith(b["section"]) else ""
            chunks.append({
                "chunk_id": chunk_id,
                "text": f"{prefix}\n{b['text']}" if prefix else b["text"],
                "metadata": {**meta, "chunk_id": chunk_id, "chunk_type": b["kind"],
                             "section": b["section"], "location": b["location"]},
            })
    return chunks


def context_text(chunk: dict) -> str:
    """The passage plus its document context: title, section and, for price lists, status and
    effective period. Used for keyword ranking, and for embedding price-list rows. The stored
    passage text is unchanged, and provenance labels are never included (spec §6B)."""
    meta = chunk["metadata"]
    parts = [meta["title"]]
    if meta["doc_type"] == "price_list":
        status = "current approved" if meta["approval_status"] == "approved" and not meta["effective_to"] \
            else meta["approval_status"]
        parts.append(f"{status} price list, effective {meta['effective_from']} to {meta['effective_to'] or 'present'}")
    if meta["section"] and meta["section"] != meta["title"]:
        parts.append(meta["section"])
    parts.append(chunk["text"])
    return " | ".join(parts)


def embedding_text(chunk: dict) -> str:
    """Price-list rows are embedded with their context, because rows from different price lists
    are otherwise near-identical. Other passages are embedded as-is: adding titles everywhere
    made proposals outrank the price list for price questions (measured regression on R3)."""
    return context_text(chunk) if chunk["metadata"]["doc_type"] == "price_list" else chunk["text"]


def build_kb_index(chroma_dir: Path = config.CHROMA_DIR, manifest: list[dict] | None = None):
    chunks = load_kb_chunks(manifest)
    for c in chunks:
        check_chunk_metadata(c["metadata"])
    client = _client(chroma_dir)
    if KB_COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(KB_COLLECTION)
    collection = client.create_collection(KB_COLLECTION, embedding_function=None,
                                          metadata={"hnsw:space": "cosine"})
    collection.add(ids=[c["chunk_id"] for c in chunks], documents=[c["text"] for c in chunks],
                   embeddings=embed([embedding_text(c) for c in chunks]),
                   metadatas=[c["metadata"] for c in chunks])
    return collection


def _where(company_id, origin, global_only):
    clauses = []
    if company_id:
        clauses.append({"$or": [{"customer_org_id": company_id}, {"subject_org_id": company_id},
                                {"scope": "global"}]})
    elif global_only:
        clauses.append({"scope": "global"})
    if origin:
        clauses.append({"info_origin": origin})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def to_evidence(chunk_id: str, text: str, meta: dict, registry: dict, rank=None, distance=None) -> dict:
    orgs = [{**o, "name": registry[o["org_id"]]["name"], "reality": registry[o["org_id"]]["reality"]}
            for o in json.loads(meta["organizations_json"])]
    return {"evidence_id": chunk_id, "rank": rank, "distance": distance, "text": text,
            "document_id": meta["document_id"], "info_origin": meta["info_origin"],
            "creation_method": meta["creation_method"], "organizations": orgs,
            "provenance_label": meta["provenance_label"], "metadata": meta}


def passages_where(where: dict, chroma_dir: Path = config.CHROMA_DIR) -> list[dict]:
    """All indexed passages matching a metadata filter, as labelled evidence in document and passage order
    (read-only lookup, no ranking)."""
    registry = load_registry()
    got = _client(chroma_dir).get_collection(KB_COLLECTION, embedding_function=None).get(
        where=where, include=["documents", "metadatas"])
    order = lambda x: (x[0].split("#")[0], int(x[0].split("#")[1]))  # noqa: E731
    return [to_evidence(cid, doc, meta, registry) for cid, doc, meta in
            sorted(zip(got["ids"], got["documents"], got["metadatas"]), key=order)]


def document_passages(document_id: str, chroma_dir: Path = config.CHROMA_DIR) -> list[dict]:
    """All indexed passages of one document as labelled evidence (read-only lookup by document ID)."""
    return passages_where({"document_id": document_id}, chroma_dir)


_STOPWORDS = set("a an the of to in on for and or is are was were what which who how did do does "
                 "we our us it its with by at from this that be".split())
RRF_K = 60
CANDIDATES = 20


def _tokens(text: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower()):
        if t in _STOPWORDS:
            continue
        for suffix in ("ing", "es", "ed", "al", "s", "e"):  # crude stemming: propose/proposal/proposes
            if t.endswith(suffix) and len(t) - len(suffix) >= 4:
                t = t[: -len(suffix)]
                break
        out.append(t)
    return out


def bm25_rank(query: str, docs: dict[str, str], k1: float = 1.5, b: float = 0.75) -> list[str]:
    """Rank document ids by BM25 score (only ids with a positive score)."""
    toks = {cid: _tokens(t) for cid, t in docs.items()}
    if not toks:
        return []
    n, avg = len(toks), sum(map(len, toks.values())) / len(toks)
    df = Counter(w for ws in toks.values() for w in set(ws))
    scores = {}
    for cid, ws in toks.items():
        tf, s = Counter(ws), 0.0
        for w in set(_tokens(query)):
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(ws) / avg))
        scores[cid] = s
    return [cid for cid, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0]


def search(text: str, k: int = 5, company_id: str | None = None, origin: str | None = None,
           global_only: bool = False, chroma_dir: Path = config.CHROMA_DIR) -> list[dict]:
    """Hybrid search. Company scope = that company's documents plus global (vendor-wide) documents.
    Both rankings use exactly the same scope and origin filter."""
    registry = load_registry()
    collection = _client(chroma_dir).get_collection(KB_COLLECTION, embedding_function=None)
    where = _where(company_id, origin, global_only)
    vec = collection.query(query_embeddings=embed([text]), n_results=max(CANDIDATES, k), where=where)
    distances = dict(zip(vec["ids"][0], vec["distances"][0]))
    pool = collection.get(where=where, include=["documents", "metadatas"])
    records = {cid: (doc, meta) for cid, doc, meta in zip(pool["ids"], pool["documents"], pool["metadatas"])}
    lexical = bm25_rank(text, {cid: context_text({"text": d, "metadata": m}) for cid, (d, m) in records.items()})

    fused = Counter()
    for rank, cid in enumerate(vec["ids"][0]):
        fused[cid] += 1 / (RRF_K + rank + 1)
    for rank, cid in enumerate(lexical[:max(CANDIDATES, k)]):
        fused[cid] += 1 / (RRF_K + rank + 1)
    return [to_evidence(cid, *records[cid], registry, rank=i + 1, distance=distances.get(cid))
            for i, (cid, _) in enumerate(fused.most_common(k))]


def _norm(name: str) -> str:
    s = re.sub(r"[^\w\s]", " ", name.casefold().replace("&", " and "))
    return " ".join(t for t in s.split() if t not in {"ltd", "inc", "limited", "plc"})


def resolve_company(name: str, domain: str | None = None, registry: dict | None = None) -> dict:
    """Map user input to a real registry organization. Never guesses between candidates.

    Matches on exact name/alias, or on the first word of a name/alias (so a bare "Arup" also
    matches "ARUP Laboratories" and is reported as ambiguous). A domain hint disambiguates.
    """
    registry = load_registry() if registry is None else registry
    real = {oid: o for oid, o in registry.items() if o["reality"] == "real"}
    if domain:
        d = domain.casefold().removeprefix("https://").removeprefix("www.").strip("/")
        matches = [oid for oid, o in real.items() if o["official_domain"] == d]
    else:
        q = _norm(name)
        matches = []
        for oid, o in real.items():
            names = [_norm(n) for n in [o["name"], *o.get("aliases", [])]]
            if q and (q in names or q in {n.split()[0] for n in names if n}):
                matches.append(oid)
    status = {0: "unresolved", 1: "resolved"}.get(len(matches), "ambiguous")
    return {"status": status, "org_id": matches[0] if status == "resolved" else None,
            "candidates": sorted(matches)}
