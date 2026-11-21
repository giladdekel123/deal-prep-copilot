"""Semantic index of APPROVED meeting records only (Prompt 06 step 5; spec §6, FR-14).

SQLite is the source of truth; Chroma (collection dms_history_v1) is only an index of approved records,
each linked back to its SQLite meeting_id. Drafts are never indexed. Approving, editing or changing
a linked task's status re-syncs that meeting's entry; reconcile() removes stale entries and restores
missing ones, so a crash between the SQLite commit and the index write is repaired by a retry.
Every entry is labelled as a SYNTHETIC, user-entered demonstration record (not a verified fact).

Known limitation (carried into Prompt 07): one local test run on 2026-11-06 failed with Chroma 1.1.1
"Error creating hnsw segment reader: Nothing found on disk". It did not recur in 450 stress iterations,
25 repeated end-to-end flows, 12 repeated history test runs and the full suite. The cause is unconfirmed
and the failing collection was not identified, so it may have been a knowledge-base query (no retry).
Index initialization, test cleanup, cache eviction and concurrent access were investigated and found
unlikely. search_history retries once with a RuntimeWarning, then raises.
"""
import json
import warnings
from pathlib import Path

from chromadb.errors import InternalError

from deal_prep import config
from deal_prep.history import HistoryStore
from deal_prep.index import _client, embed

HISTORY_COLLECTION = "dms_history_v1"
VENDOR_ORG = "nivarque"


def _collection(chroma_dir: Path):
    return _client(chroma_dir).get_or_create_collection(HISTORY_COLLECTION, embedding_function=None,
                                                         metadata={"hnsw:space": "cosine"})


def _entry_id(meeting_id: str) -> str:
    return f"HIST-{meeting_id}#0"


def provenance_label(meeting: dict) -> str:
    when = meeting["meeting_date"] or "date not recorded"
    return (f"SYNTHETIC — user-entered demonstration meeting record ({when}; approved {meeting['approved_at'][:10]}); "
            f"not a verified real-world fact")


def meeting_text(meeting: dict, tasks: list[dict]) -> str:
    a = meeting["approved"] or {}
    lines = [f"Meeting record ({meeting['meeting_date'] or 'date not recorded'}): {a.get('summary', '')}"]
    for key, title in (("participants", "Participants"), ("concerns", "Concerns raised"),
                       ("decisions", "Decisions"), ("commitments", "Commitments")):
        if a.get(key):
            lines.append(f"{title}: " + "; ".join(a[key]))
    for t in tasks:
        due = t["due_date"] or (f"not confirmed ('{t['due_raw']}')" if t["due_raw"] else "none")
        lines.append(f"Follow-up task ({t['status']}, due {due}): {t['description']}")
    return "\n".join(lines)


def sync_meeting(store: HistoryStore, meeting_id: str, chroma_dir: Path = config.CHROMA_DIR) -> None:
    """Make the index match SQLite for one meeting: approved -> (re)indexed; otherwise removed."""
    meeting = store.meeting(meeting_id)
    col = _collection(chroma_dir)
    col.delete(ids=[_entry_id(meeting_id)])
    if meeting["status"] != "APPROVED":
        return
    company = store.company(meeting["company_id"])
    text = meeting_text(meeting, store.tasks(meeting_id=meeting_id))
    orgs = [{"org_id": VENDOR_ORG, "role": "vendor"}] + (
        [{"org_id": company["org_id"], "role": "customer"}] if company["org_id"] else [])
    col.add(ids=[_entry_id(meeting_id)], documents=[text], embeddings=embed([text]), metadatas=[{
        "meeting_id": meeting_id, "company_id": meeting["company_id"], "document_id": f"HIST-{meeting_id}",
        "doc_type": "meeting_record", "info_origin": "synthetic_record",
        "creation_method": meeting["creation_method"], "approval_status": "approved",
        "approved_at": meeting["approved_at"], "effective_from": meeting["meeting_date"] or "",
        "customer_org_id": company["org_id"] or "", "conflict_group": "", "scope": "company",
        "organizations_json": json.dumps(orgs), "provenance_label": provenance_label(meeting)}])


def reconcile(store: HistoryStore, chroma_dir: Path = config.CHROMA_DIR) -> dict:
    """Remove index entries with no approved SQLite record; (re)index every approved record."""
    col = _collection(chroma_dir)
    approved = {m["meeting_id"] for m in store.approved_meetings()}
    indexed = {m["meeting_id"] for m in col.get(include=["metadatas"])["metadatas"]}
    stale = sorted(indexed - approved)
    if stale:
        col.delete(ids=[_entry_id(m) for m in stale])
    for meeting_id in sorted(approved):
        sync_meeting(store, meeting_id, chroma_dir)
    return {"removed": stale, "indexed": sorted(approved)}


def search_history(store: HistoryStore, company_id: str, query: str, k: int = 3,
                   chroma_dir: Path = config.CHROMA_DIR) -> list[dict]:
    """Company-scoped approved history as labelled evidence objects (SQLite remains authoritative)."""
    col = _collection(chroma_dir)
    if col.count() == 0:
        return []
    try:
        res = col.query(query_embeddings=embed([query]), n_results=min(k, col.count()),
                        where={"company_id": company_id})
    except InternalError as e:  # observed once in local tests (cause unconfirmed): retry once, visibly, then raise
        warnings.warn(f"history index query retried once after: {e}", RuntimeWarning, stacklevel=2)
        col = _collection(chroma_dir)
        res = col.query(query_embeddings=embed([query]), n_results=min(k, col.count()),
                        where={"company_id": company_id})
    out = []
    for cid, text, meta in zip(res["ids"][0], res["documents"][0], res["metadatas"][0]):
        try:
            meeting = store.meeting(meta["meeting_id"])
        except KeyError:  # entry left by a record that no longer exists in SQLite
            continue
        if meeting["status"] != "APPROVED":  # SQLite is authoritative: never trust a stale index entry
            continue
        orgs = json.loads(meta["organizations_json"])
        # The text is rebuilt from SQLite, so current task statuses win over a possibly stale index copy.
        current = meeting_text(meeting, store.tasks(meeting_id=meta["meeting_id"]))
        out.append({"evidence_id": cid, "text": current, "document_id": meta["document_id"],
                    "info_origin": "synthetic_record", "creation_method": meta["creation_method"],
                    "organizations": [{**o, "reality": "fictional" if o["org_id"] == VENDOR_ORG else "real"}
                                      for o in orgs],
                    "provenance_label": meta["provenance_label"], "metadata": meta})
    return out


# --- I1: structured meeting history for briefings, straight from SQLite -------------------------------

MAX_MEETINGS = 5           # meeting records passed to the drafter per briefing
MAX_TASKS = 12             # follow-up tasks per meeting record
MAX_LIST_ITEMS = 8         # entries per list field (participants, concerns, decisions, commitments)
FIELD_WORDS = 40           # words per text entry
UNRESOLVED = ("Open", "In Progress")


def _cap(text: str, words: int = FIELD_WORDS) -> str:
    parts = (text or "").split()
    return " ".join(parts[:words]) + (" …" if len(parts) > words else "")


def _capped_list(values, label: str) -> tuple[list[str], str | None]:
    values = [v for v in (values or []) if str(v).strip()]
    note = f"{len(values) - MAX_LIST_ITEMS} further {label} not shown" if len(values) > MAX_LIST_ITEMS else None
    return [_cap(str(v)) for v in values[:MAX_LIST_ITEMS]], note


def meeting_record(meeting: dict, tasks: list[dict]) -> dict:
    """The structured fields of one approved meeting record, with current task statuses (SQLite)."""
    a = meeting["approved"] or {}
    record = {"meeting_id": meeting["meeting_id"], "meeting_date": meeting["meeting_date"] or "date not recorded",
              "approval_status": "approved", "approved_at": (meeting["approved_at"] or "")[:10],
              "summary": _cap(a.get("summary", "")), "omissions": []}
    for key, label in (("participants", "participants"), ("concerns", "concerns"), ("decisions", "decisions"),
                       ("commitments", "commitments")):
        record[key], note = _capped_list(a.get(key), label)
        if note:
            record["omissions"].append(note)
    record["follow_up_tasks"] = [
        {"description": _cap(t["description"]), "status": t["status"],
         "due_date": t["due_date"] or (f"not confirmed ('{t['due_raw']}')" if t["due_raw"] else "none")}
        for t in tasks[:MAX_TASKS]]
    if len(tasks) > MAX_TASKS:
        record["omissions"].append(f"{len(tasks) - MAX_TASKS} further follow-up tasks not shown")
    return record


def _newest_first(meetings: list[dict]) -> list[dict]:
    return sorted(meetings, key=lambda m: (m["meeting_date"] or "", m["approved_at"] or ""), reverse=True)


def company_history(store: HistoryStore, company_id: str, max_meetings: int = MAX_MEETINGS) -> list[dict]:
    """Every APPROVED meeting record of this company, from SQLite (the authoritative store), newest first.

    Eligibility is decided here, not by semantic similarity: drafts and other companies' records are excluded
    by the query itself. If there are more than max_meetings, meetings with an unresolved task (Open or In
    Progress) are kept first, then the newest others; the omission is stated in the newest record."""
    company = store.company(company_id)
    if company is None:
        return []
    approved = _newest_first(store.meetings(company_id, status="APPROVED"))
    tasks = {m["meeting_id"]: store.tasks(meeting_id=m["meeting_id"]) for m in approved}
    unresolved = [m for m in approved if any(t["status"] in UNRESOLVED for t in tasks[m["meeting_id"]])]
    keep_ids = {m["meeting_id"] for m in (unresolved + [m for m in approved if m not in unresolved])[:max_meetings]}
    kept = [m for m in approved if m["meeting_id"] in keep_ids]
    omitted = len(approved) - len(kept)
    omitted_open = sum(1 for m in unresolved if m["meeting_id"] not in keep_ids)
    orgs = [{"org_id": VENDOR_ORG, "role": "vendor", "reality": "fictional"}] + (
        [{"org_id": company["org_id"], "role": "customer", "reality": "real"}] if company["org_id"] else [])
    out = []
    for i, m in enumerate(kept):
        record = meeting_record(m, tasks[m["meeting_id"]])
        if i == 0 and omitted:
            record["omissions"].append(f"{omitted} older approved meeting records are not shown"
                                       + (f" ({omitted_open} of them with open tasks)" if omitted_open else
                                          " (none of them has an open task)"))
        meta = {"meeting_id": m["meeting_id"], "company_id": company_id, "document_id": f"HIST-{m['meeting_id']}",
                "doc_type": "meeting_record", "info_origin": "synthetic_record",
                "creation_method": m["creation_method"], "approval_status": "approved",
                "approved_at": m["approved_at"], "effective_from": m["meeting_date"] or "",
                "customer_org_id": company["org_id"] or "", "conflict_group": "", "scope": "company",
                "provenance_label": provenance_label(m)}
        out.append({"evidence_id": _entry_id(m["meeting_id"]), "text": meeting_text(m, tasks[m["meeting_id"]]),
                    "record": record, "document_id": meta["document_id"], "info_origin": "synthetic_record",
                    "creation_method": m["creation_method"], "organizations": orgs,
                    "provenance_label": meta["provenance_label"], "metadata": meta})
    return out
