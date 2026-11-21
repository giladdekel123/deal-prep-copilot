"""Uniform, sanitized view of all evidence in a research bundle (internal, external, supplemental).

Used to build what the agent and the drafting model may see: evidence ID, origin, provenance
label and a short excerpt. Never credentials, never full documents.
"""
EXCERPT_WORDS = 60
# Approved meeting records (I1): every structured line is kept, each capped, so follow-up tasks and their
# current statuses are never cut off by the general excerpt limit. The record is user-approved synthetic data
# for the selected company only (already filtered by company and approval status).
MEETING_LINE_WORDS = 40
MEETING_MAX_TASKS = 12
TASK_PREFIX = "Follow-up task"


def _short(text: str, words: int = EXCERPT_WORDS) -> str:
    parts = (text or "").split()
    return " ".join(parts[:words]) + (" …" if len(parts) > words else "")


def meeting_excerpt(text: str) -> str:
    """Structured excerpt of a meeting record: header, participants, concerns, decisions and commitments, then up
    to MEETING_MAX_TASKS follow-up tasks with status and due date; anything left out is stated, never silent."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    head = [_short(ln, MEETING_LINE_WORDS) for ln in lines if not ln.startswith(TASK_PREFIX)]
    tasks = [_short(ln, MEETING_LINE_WORDS) for ln in lines if ln.startswith(TASK_PREFIX)]
    out = head + tasks[:MEETING_MAX_TASKS]
    if len(tasks) > MEETING_MAX_TASKS:
        out.append(f"[{len(tasks) - MEETING_MAX_TASKS} further follow-up tasks not shown]")
    return "\n".join(out)


def normalize(e: dict, source: str) -> dict:
    """Common shape for knowledge-base evidence (kb_index) and web evidence (web_research)."""
    meta = e.get("metadata", {})
    text = e.get("excerpt") or e.get("text", "")
    is_meeting = meta.get("doc_type") == "meeting_record" and meta.get("approval_status") == "approved"
    out = {"evidence_id": e["evidence_id"], "source": source, "info_origin": e["info_origin"],
           "provenance_label": e["provenance_label"],
           "excerpt": meeting_excerpt(text) if is_meeting else _short(text),
           "time_window": e.get("time_window"), "document_id": e.get("document_id"),
           "approval_status": meta.get("approval_status") or None,
           "conflict_group": meta.get("conflict_group") or None,
           "customer_org_id": meta.get("customer_org_id") or None}
    if is_meeting and e.get("record"):  # I1: structured fields (identity, date, approval, tasks with status)
        out["meeting_record"] = e["record"]
    if e.get("dateline"):  # I7: a news release's own place-and-date line (web_research)
        out["dateline"] = e["dateline"]
    return out


def kb_evidence(bundle: dict) -> list[dict]:
    """Raw knowledge-base evidence objects (with full metadata), mandatory and supplemental."""
    out = [e for block in bundle.get("internal", {}).values() for e in block["evidence"]]
    out += [e for e in bundle.get("supplemental", []) if "metadata" in e]
    seen = {e["evidence_id"] for e in out}
    # Exact passages fetched for disclosed conflicts (so each quoted statement has its own citation).
    return out + [e for e in bundle.get("conflict_sources", []) if e["evidence_id"] not in seen]


# CP-2 (owner-approved): the evidence profile is part of what the drafting model and the research agent see.
# Switchable only for a controlled with/without comparison by the evaluation scripts.
PROFILE_IN_MODEL_INPUT = True


def model_evidence(bundle: dict) -> list[dict]:
    """The sanitized evidence a model receives: evidence_index entries plus, under CP-2, each entry's profile
    (source class, statement form, date status; contested_with / restates only when not empty)."""
    from deal_prep.evidence_profile import profile

    entries = list(evidence_index(bundle).values())
    if not PROFILE_IN_MODEL_INPUT:
        return entries
    from datetime import date
    as_of = date.fromisoformat(bundle["created_at"][:10]) if bundle.get("created_at") else None  # I7
    prof = profile(entries, (bundle.get("identity") or {}).get("domain"), as_of=as_of)
    return [{**e, "profile": {k: v for k, v in prof[e["evidence_id"]].items() if v != []}} for e in entries]


def evidence_index(bundle: dict) -> dict[str, dict]:
    index = {}
    for topic, block in bundle.get("internal", {}).items():
        for e in block["evidence"]:
            index[e["evidence_id"]] = normalize(e, f"internal:{topic}")
    for e in (bundle.get("external") or {}).get("evidence", []):
        index[e["evidence_id"]] = normalize(e, "external_news")
    for e in bundle.get("supplemental", []):
        index[e["evidence_id"]] = normalize(e, f"supplemental:{e.get('_tool', 'agent')}")
    for e in bundle.get("conflict_sources", []):
        index.setdefault(e["evidence_id"], normalize(e, "internal:conflict_sources"))
    return index
