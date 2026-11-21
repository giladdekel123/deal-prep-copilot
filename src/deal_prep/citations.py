"""Deterministic evidence, citation and disclosure validation (Prompt 04 steps 4–5).

Runs after the schema check. For every cited evidence ID:
1. existence: the ID must be one of the evidence objects in the research bundle;
2. origin: for a fact, the evidence origin must match the claim type (authority.CLAIM_ORIGINS):
   real-world facts and publicly disclosed pricing need public sources; relationship, meeting,
   vendor product and vendor price claims need synthetic records;
3. recency: a fact in recent_developments must cite dated news from the 48-hour or 30-day window,
   never undated results or curated public snapshots; I7: or a public document whose stated publication date falls
   within that window.
Step 5 adds rules that stop uncertainty becoming confident claims:
4. a fact may not cite draft or superseded evidence;
5. a fact may not cite evidence from an unresolved conflict (it would pick a side);
6. a relationship or meeting fact must cite records tied to this customer;
7. every required disclosure must be acknowledged by ID, and every empty section explained;
8. I7.1 (conflict_guard): a claim that public statements conflict must cite both sides of an established conflict;
   statements the evidence shows compatible may not be called conflicting, and a disagreement no check establishes
   may only be stated as an inference that must be verified.
Inferences and recommendations get the existence check only; they are labelled as analysis.
Whether the cited passage actually supports the claim (entailment) is a separate check.
"""
from datetime import date

from deal_prep.authority import CLAIM_ORIGINS
from deal_prep.disclosures import derived, one_sided_claims, required_disclosures, unresolved_conflicts
from deal_prep.evidence import evidence_index

RECENT_WINDOWS = {"last_48h", "last_30_days"}
NON_AUTHORITATIVE = {"draft", "superseded"}
CUSTOMER_CLAIMS = {"relationship", "meeting_history"}


def validate_citations(draft: dict, bundle: dict) -> dict:
    index = evidence_index(bundle)
    as_of = date.fromisoformat(bundle["created_at"][:10])
    conflicted = set(unresolved_conflicts(bundle, as_of))
    company = (bundle.get("identity") or {}).get("org_id")
    issues = []

    def issue(section, i, eid, code, message):
        issues.append({"section": section, "item": i, "evidence_id": eid, "code": code, "message": message})

    for section, items in draft["sections"].items():
        for i, item in enumerate(items):
            for eid in item["evidence_ids"]:
                ev = index.get(eid)
                if ev is None:
                    issue(section, i, eid, "nonexistent_citation",
                          f"{eid} is not in the research results (invented or mistyped citation)")
                    continue
                if item["kind"] != "fact":
                    continue
                needed = CLAIM_ORIGINS[item["claim_type"]]
                if ev["info_origin"] != needed:
                    issue(section, i, eid, "origin_violation",
                          f"a {item['claim_type']} fact needs {needed} evidence, but {eid} is {ev['info_origin']}")
                if section == "recent_developments" and ev["time_window"] not in RECENT_WINDOWS \
                        and not _recent_official(ev, as_of):
                    issue(section, i, eid, "not_recent_evidence",
                          f"{eid} is not dated news from the last 48 hours or 30 days "
                          f"(window: {ev['time_window'] or 'curated snapshot'})")
                if ev["approval_status"] in NON_AUTHORITATIVE:
                    issue(section, i, eid, "non_authoritative_evidence",
                          f"{eid} is {ev['approval_status']}; it cannot support a fact")
                if ev["conflict_group"] in conflicted:
                    issue(section, i, eid, "unresolved_conflict_as_fact",
                          f"{eid} belongs to unresolved conflict {ev['conflict_group']}; state it as a "
                          f"disclosed disagreement, not as a fact")
                if item["claim_type"] in CUSTOMER_CLAIMS and ev["customer_org_id"] != company:
                    issue(section, i, eid, "not_this_customer",
                          f"{eid} is not a record of the relationship with this company")

    # I4: a fact that cites one side of a derived conflict must cite every side (it may report the disagreement as a
    # fact, but it may not silently drop one side).
    for c in derived(bundle):
        ids = {s["evidence_id"] for s in c["sides"]}
        for section, items in draft["sections"].items():
            for i, item in enumerate(items):
                cited = ids & set(item["evidence_ids"])
                if item["kind"] == "fact" and cited and cited != ids:
                    issue(section, i, sorted(cited)[0], "conflict_side_dropped",
                          f"{sorted(cited)} is one side of {c['kind'].replace('_', ' ')} {c['id']}; a fact citing it "
                          f"must also cite {sorted(ids - cited)} and present both, or be stated as an inference")

    # D2: a fact that states one side of a disputed capability as established is refused, whatever it cites, when the
    # briefing is about a conflict that was set aside as irrelevant (the safety rule discloses it; the claim must not
    # contradict that). Run here so the retry, the last resort and the final validation all see it.
    for section, i, g in one_sided_claims(bundle, draft, as_of):
        cited = draft["sections"][section][i]["evidence_ids"]
        issue(section, i, cited[0] if cited else None, "one_sided_conflict_claim",
              f"this fact states one side of unresolved conflict {g} between the vendor's own documents as "
              f"established; state that the documents disagree, or ask the question; do not choose a side")

    acknowledged = {d["id"] for d in draft.get("disclosures", [])}
    for d in required_disclosures(bundle, as_of):
        if d["id"] not in acknowledged:
            issue("disclosures", None, None, "missing_disclosure", f"required disclosure {d['id']} missing: {d['text']}")
    for section, items in draft["sections"].items():
        if not items and f"empty_section:{section}" not in acknowledged:
            issue(section, None, None, "unexplained_empty_section",
                  f"{section} is empty; add disclosure empty_section:{section} explaining what is missing")
    from deal_prep import conflict_guard  # I7.1: a conflict claim must be established, or stated as to be verified
    issues += conflict_guard.check(draft, bundle)
    return {"valid": not issues, "issues": issues}


def _recent_official(ev: dict, as_of: date) -> bool:
    """I7: a public document whose stated publication date falls within the news window is a recent development."""
    from deal_prep import company_context, evidence_profile
    return company_context.ENABLED and evidence_profile.recent_official(ev, as_of, company_context.RECENT_DAYS)


def issues_summary(issues: list[dict]) -> str:
    return "; ".join(f"{x['section']}[{x['item']}] {x['code']}: {x['message']}" for x in issues)
