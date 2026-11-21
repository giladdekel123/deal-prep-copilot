"""Deterministic authority and origin rules (spec v1.2 FR-07, §8), separate from retrieval.

Retrieval returns whatever is relevant, including superseded, draft or conflicting passages.
These functions decide what a passage may support. Each returns:
    {"status": resolved | unresolved | no_valid_source | origin_violation,
     "selected": [evidence_id], "rejected": [(evidence_id, reason)],
     "origin_violations": [evidence_id], "value": optional}
Evidence objects are dicts with "evidence_id", "text" and "metadata" (see kb_index.to_evidence).
"""
from datetime import date

# Synthetic records cannot prove real-world facts; public sources cannot prove the fictional
# vendor's prices, proposals, meetings or invented relationships.
CLAIM_ORIGINS = {
    "real_world_fact": "public_source",
    "public_pricing": "public_source",
    "vendor_price": "synthetic_record",
    "vendor_product": "synthetic_record",
    "relationship": "synthetic_record",
    "meeting_history": "synthetic_record",
}


def _result(status, selected=(), rejected=(), violations=(), value=None):
    return {"status": status, "selected": list(selected), "rejected": list(rejected),
            "origin_violations": list(violations), "value": value}


def _split_by_origin(claim_type, evidence):
    allowed = CLAIM_ORIGINS[claim_type]
    ok = [e for e in evidence if e["metadata"]["info_origin"] == allowed]
    bad = [e["evidence_id"] for e in evidence if e["metadata"]["info_origin"] != allowed]
    return ok, bad


def _in_force(meta, as_of: date) -> bool:
    start, end = meta.get("effective_from"), meta.get("effective_to")
    if start and date.fromisoformat(start) > as_of:
        return False
    return not end or as_of <= date.fromisoformat(end)


def _row_fields(text: str) -> dict:
    body = text.splitlines()[-1]
    return dict(part.split(": ", 1) for part in body.split(" | ") if ": " in part)


def _finish(ok, violations, rejected, selected, status_if_selected, value=None):
    """origin_violation only when every piece of evidence had the wrong origin; if right-origin
    evidence existed but none qualified, the answer is no_valid_source."""
    if selected:
        return _result(status_if_selected, selected, rejected, violations, value)
    if violations and not ok:
        return _result("origin_violation", (), rejected, violations)
    return _result("no_valid_source", (), rejected, violations)


def current_list_price(evidence, product: str, tier: str, as_of: date):
    """Price list in force on as_of decides. A proposal price is never a list price (C3)."""
    ok, violations = _split_by_origin("vendor_price", evidence)
    rejected, candidates = [], {}
    for e in ok:
        meta = e["metadata"]
        if meta.get("chunk_type") != "table_row":
            continue
        row = _row_fields(e["text"])
        if row.get("Product") != product or row.get("Tier") != tier:
            continue
        if meta["doc_type"] == "proposal":
            rejected.append((e["evidence_id"], "proposal price is a negotiated historical offer, not a list price"))
        elif meta["doc_type"] != "price_list":
            continue
        elif meta["approval_status"] == "draft":
            rejected.append((e["evidence_id"], "draft price list"))
        elif not _in_force(meta, as_of):
            rejected.append((e["evidence_id"], f"price list not in force on {as_of.isoformat()} "
                                               f"(status {meta['approval_status']})"))
        else:
            candidates[e["evidence_id"]] = row.get("List price (USD)")
    if len(set(candidates.values())) > 1:
        return _result("unresolved", candidates, rejected, violations)
    value = next(iter(candidates.values()), None)
    return _finish(ok, violations, rejected, candidates, "resolved", value)


def historical_offer(evidence, company_id: str, product: str):
    """What did we offer this company? Synthetic proposals for that company decide; labelled historical."""
    ok, violations = _split_by_origin("relationship", evidence)
    selected, values, rejected = [], [], []
    for e in ok:
        meta = e["metadata"]
        if meta["doc_type"] != "proposal" or meta.get("chunk_type") != "table_row":
            continue
        if meta.get("customer_org_id") != company_id:
            rejected.append((e["evidence_id"], "proposal for a different company"))
            continue
        row = _row_fields(e["text"])
        if row.get("Product") == product:
            selected.append(e["evidence_id"])
            values.append(row.get("Proposed price (USD)"))
    value = {"proposed_price_usd": values, "label": "historical synthetic proposal"} if selected else None
    return _finish(ok, violations, rejected, selected, "resolved", value)


def policy_statement(evidence, as_of: date):
    """Approved, in-force vendor statements decide; disagreeing approved documents stay unresolved (C2)."""
    ok, violations = _split_by_origin("vendor_product", evidence)
    selected, rejected = [], []
    for e in ok:
        meta = e["metadata"]
        if meta["approval_status"] != "approved":
            rejected.append((e["evidence_id"], f"status {meta['approval_status']}"))
        elif not _in_force(meta, as_of):
            rejected.append((e["evidence_id"], f"not in force on {as_of.isoformat()}"))
        else:
            selected.append(e)
    groups = {}
    for e in selected:
        if e["metadata"].get("conflict_group"):
            groups.setdefault(e["metadata"]["conflict_group"], set()).add(e["metadata"]["document_id"])
    status = "unresolved" if any(len(docs) > 1 for docs in groups.values()) else "resolved"
    return _finish(ok, violations, rejected, [e["evidence_id"] for e in selected], status)


def meeting_history(evidence):
    """Only approved meeting notes count; drafts never become history."""
    ok, violations = _split_by_origin("meeting_history", evidence)
    selected, rejected = [], []
    for e in ok:
        meta = e["metadata"]
        if meta["doc_type"] != "meeting_notes":
            continue
        if meta["approval_status"] == "approved":
            selected.append(e["evidence_id"])
        else:
            rejected.append((e["evidence_id"], f"meeting notes with status {meta['approval_status']} never count"))
    return _finish(ok, violations, rejected, selected, "resolved")


def real_world_fact(evidence):
    """Public sources only. Synthetic evidence is an origin violation (C4). Disagreeing public
    sources in the same conflict group stay unresolved; neither is chosen."""
    ok, violations = _split_by_origin("real_world_fact", evidence)
    groups = {}
    for e in ok:
        if e["metadata"].get("conflict_group"):
            groups.setdefault(e["metadata"]["conflict_group"], set()).add(e["metadata"]["document_id"])
    status = "unresolved" if any(len(docs) > 1 for docs in groups.values()) else "resolved"
    return _finish(ok, violations, [], [e["evidence_id"] for e in ok], status)
