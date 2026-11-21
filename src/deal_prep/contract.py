"""Phase 4.5 I3.1 (early CP-3, owner-approved 2026-11-11): the meeting-purpose drafting contract and a final-output
coverage check.

I3 made the right evidence reach the drafter; the live drafter still did not always communicate it (a product demo
without product content, negotiations without the list price). The contract turns the meeting purpose and the
evidence actually selected into a short list of ESSENTIAL TOPICS that the briefing must address, each with the
evidence that supports it. Topics are derived by general rules from the purpose, the selection (products in play,
purpose documents), the customer's approved records and the evidence profile (contested figures). No company name,
evaluation answer or expected score is used.

coverage() then reads the FINAL briefing and classifies every topic:
  communicated  - one item cites the topic's evidence (every evidence group, e.g. both sides of a contested figure)
                  AND states some of its content (a figure, task, capability or product term from that evidence);
  cited_only    - the evidence is cited but none of its content is stated;
  gap_declared  - the model disclosed that the evidence cannot support the topic (disclosure topic_gap:<id>);
  missing       - not addressed.
This separates "in the model input" from "communicated in the briefing". It is a lexical proxy, not a judgement of
quality, and the topics are derived from the same evidence the drafter sees, so it cannot detect a topic the
selection never found.
"""
import re

from deal_prep import chronology, numbers
from deal_prep.evidence import evidence_index, kb_evidence
from deal_prep.evidence_profile import document_key, profile
from deal_prep.selection import row_product

PURPOSE_BRIEFS = {
    "negotiation": ("Negotiation: give the seller the commercial position. State what the customer has asked for, "
                    "the proposed terms and their validity, the current list price of each product in play beside "
                    "the proposed price, the discount-approval thresholds that govern any concession, and every "
                    "open commitment with its due date. Recommendations are concrete commercial moves for this "
                    "meeting."),
    "follow_up": ("Follow-up: state every unresolved customer request and commitment with its status and due date, "
                  "the date of the latest contact, what has been completed, and what the customer is waiting for. "
                  "Recommendations close the open items."),
    "product_demo": ("Product demonstration: state which documented capabilities to show and why each may matter to "
                     "this organization, using the product and security evidence (the core document control the "
                     "product evidence lists, approval workflows, retention and legal hold, security and encryption, "
                     "identity, data region and deployment, integrations). Tie each to the organization's own "
                     "evidence where possible, as something to verify, not an assumed need. Recommendations form a "
                     "demonstration plan that always starts from the core document control."),
    "introduction": ("Introduction: who the organization is, what has happened recently, and fit hypotheses that "
                     "connect documented product capabilities to plausible needs suggested by the organization's own "
                     "evidence, each labelled as a hypothesis to verify. Recommendations are discovery questions."),
    "general": ("General preparation: the organization, the relationship and the product and commercial facts most "
                "relevant to it."),
}
# Validation correction (owner-approved 2026-11-14): added to the general brief when the meeting is with a new lead and
# product descriptions were selected for it (selection.context_documents).
NEW_LEAD_GENERAL_BRIEF = ("With no relationship yet, add one or two fit hypotheses that connect documented product "
                          "capabilities to the organization's own evidence, each labelled as a hypothesis to verify, "
                          "and make the recommendations discovery questions; never state an assumed need.")
# I7 (owner-approved 2026-11-16): added when company:* topics exist (company_context).
COMPANY_CONTEXT_BRIEF = ("Prioritize: who the organization is and its most material, newest developments come first, "
                         "each with its source's date; leave out company facts that do not matter for this meeting.")
# C2 (owner-approved 2026-11-17): added instead when the only company topic is the compact company:brief.
COMPANY_BRIEF_NOTE = ("Keep the company essentials compact (one or two items in company_overview); the relationship, "
                      "commercial and open items come first.")
# I6 (owner-approved 2026-11-12): section placement and conciseness. It takes effect only together with the I5 analysis
# (briefing.i6_active); switchable only for the controlled with/without comparison by the evaluation scripts.
LAYOUT_ENABLED = True
LAYOUT_BRIEFS = {  # added to the purpose brief when I6 is active
    "negotiation": ("our_relationship carries the proposal and the commercial position (list price, discount, approval "
                    "tier) once; recommendations are the moves that follow, not a restatement."),
    "follow_up": "Start our_relationship with the latest contact and what is still open.",
    "product_demo": ("The demonstration plan is in meeting_recommendations, one item per capability area. "
                     "opportunities holds at most two fit hypotheses tied to the organization's own evidence; do not "
                     "describe a capability in both sections."),
    "introduction": ("opportunities holds the fit hypotheses; meeting_recommendations holds discovery questions, not "
                     "product pitches."),
}
# Capability areas of a document-management product demonstration (vocabulary of the vendor's domain).
# Validation correction (owner-approved 2026-11-14): core document control is its own area, checked capability by
# capability (DOCUMENT_CONTROL), separately from approval workflows. One keyword no longer satisfies the area: the
# validation found demo plans that showed approval workflows and silently dropped the core capabilities.
DEMO_AREAS = {
    "document_control": r"version control|versioning|check-in|check-out|metadata|full-text search",
    "approval_workflows": r"workflow|approval",
    "retention_and_legal_hold": r"retention|legal hold|disposal",
    "security_and_encryption": r"encrypt|AES|TLS",
    "identity_and_access": r"single sign-on|SAML|OpenID|SCIM",
    "data_region_and_deployment": r"\bregions?\b|hosted|private-cloud|single-tenant",
    "integrations": r"integration|REST API|connectors?",
}
# The core document-control capabilities of a document-management product: (label, pattern in the product evidence,
# pattern in the briefing). Only the capabilities the selected evidence documents are required, and EACH must be
# stated (require_all), so a plan naming one of them does not pass.
DOCUMENT_CONTROL = (
    ("version control", r"version control|versioning", r"version(?:s|ing| control| history)?\b"),
    ("check-in and check-out", r"check-in|check-out", r"check-in|check-out|checkin|checkout|check in and (?:check )?out"),
    ("metadata", r"metadata", r"metadata|tagg(?:ing|ed)"),
    ("search", r"full-text search|\bsearch", r"\bsearch"),
)
MAX_TOPICS = 16
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTHS})\b|\b(?:{_MONTHS})\s+\d{{1,2}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b")
_ID = re.compile(r"\b[A-Z]{2,}(?:-[A-Za-z0-9]+)+(?:#\d+)?\b")
_STOP = set("""nivarque synthetic record records customer customers proposal proposals meeting meetings account
executive demonstration fictional company organization organizations status follow-up approved because
between through should would could about their there these those which while within without concerned concern
agreed document documents management system systems provides product products""".split())


def figures(text: str) -> list[str]:
    """Figures a statement is about: numbers that are not dates, years or document IDs, each literal whole as written
    (C1: read with deal_prep.numbers; "1,569.7" is one figure, not "1,569")."""
    t = _ID.sub(" ", _DATE.sub(" ", text or ""))
    return sorted({n.literal for n in numbers.read(t) if not numbers.is_year(n.literal)})


def terms(text: str, min_len: int = 7, exclude: set = frozenset()) -> list[str]:
    """Content words of a statement (long, not generic, not the company's own name)."""
    words = re.findall(r"[A-Za-z][A-Za-z-]+", text or "")
    return sorted({w.casefold() for w in words
                   if len(w) >= min_len and w.casefold() not in _STOP and w.casefold() not in exclude})


def _num_markers(nums):
    """C1: each figure as written, or with the same certain value written with or without thousands separators."""
    return [numbers.marker(n) for n in nums]


def _word_markers(words):
    return [rf"\b{re.escape(w)}" for w in words]


def _topic(tid, section, requirement, groups, markers):
    return {"id": tid, "section": section, "requirement": requirement,
            "groups": [sorted(g) for g in groups if g], "markers": markers}


def _approval_text(policy: dict, percent: float | None) -> str:
    """The thresholds of the parsed policy, and the one that applies to the requested discount; never a grant."""
    from deal_prep import business
    if policy["status"] != "parsed":
        return ("the policy's approval conditions as the cited policy gives them (say so if the policy does not give "
                "them completely)")
    tiers = policy["tiers"]
    parts = [f"up to {tiers[0]['up_to_pct']:g}% {business._approver(tiers[0])}"]
    for n, t in enumerate(tiers[1:], 1):
        upper = f" through {tiers[n + 1]['above_pct']:g}%" if n + 1 < len(tiers) else ""
        parts.append(f"above {t['above_pct']:g}%{upper} {business._approver(t)}")
    text = "; ".join(parts)
    if percent is not None:
        text += (f". The request is for {percent:g}%, which under the policy needs "
                 f"{business._approver(business._tier_for(percent, policy))}")
    return text


_NOT_GRANTED = ("Say what approval the policy requires; do not state or imply that any approval has been granted or "
                "that the discount will be offered.")


def _approval_requirement(bundle: dict, topics: list[dict], raw: dict, reasons: dict, purpose: str) -> None:
    """D1: when the customer's approved records ask for commercial terms and the policy with discount approval
    thresholds is in the drafting input, require its approval authority and conditions to be stated. A negotiation
    already has the approval_policy topic: it gains the request instead of a second topic."""
    from deal_prep import business, company_context, selection
    asked = selection.commercial_request_sentence(company_context.approved_records(bundle))
    policy_ids = [eid for eid, e in raw.items() if (e.get("metadata") or {}).get("doc_type") == "policy"
                  and reasons.get(eid, "").startswith("purpose_document:") and re.search(r"discount", e["text"], re.I)]
    if not asked or not policy_ids:
        return
    eid, sentence = asked
    percent = selection.requested_percent(sentence)
    policy = business.approval_policy([raw[i] for i in policy_ids])
    detail = _approval_text(policy, percent)
    if purpose == "negotiation":
        for t in topics:
            if t["id"] == "approval_policy":
                t["requirement"] += (f" The customer's approved record {eid} asks for commercial terms: {detail}. "
                                     + _NOT_GRANTED)
        return
    figs = figures(" ".join(raw[i]["text"] for i in policy_ids))
    tier = business._tier_for(percent, policy) if percent is not None and policy["status"] == "parsed" else None
    words = tier["approver"].casefold().split() if tier else []
    if words and len(words[-1]) > 3:
        words[-1] = words[-1].rstrip("s")  # "account executives" is also matched as "account executive"
    markers = [r"\s+".join(re.escape(w) for w in words)] if tier else _num_markers(figs)
    topics.append(_topic("approval_requirement", "meeting_recommendations",
                         f"The customer's approved record {eid} asks for commercial terms. State the approval the "
                         f"policy requires: {detail}. " + _NOT_GRANTED, [policy_ids], markers))


def essential_topics(bundle: dict, analysis: dict | None = None, layout: bool = False) -> list[dict]:
    """The topics this meeting's briefing must address, each with its supporting evidence (groups of IDs) and the
    content markers coverage() looks for. Only evidence present in the drafting input is used.
    layout (I6): the same topics, with the I6 section and wording (one home per fact)."""
    purpose = bundle.get("purpose") or "general"
    index = evidence_index(bundle)
    raw = {e["evidence_id"]: e for e in kb_evidence(bundle)}
    sel = bundle.get("selection") or {}
    reasons = sel.get("selected", {})
    products = sel.get("products_in_play", [])
    org = (bundle.get("identity") or {}).get("org_id")
    name_words = {w.casefold() for w in re.findall(r"[A-Za-z-]+", (bundle.get("identity") or {}).get("name", ""))}
    topics = []

    # Customer records (any purpose): requests, proposal terms, commitments.
    docs: dict[str, list[dict]] = {}
    for eid, e in index.items():
        meta = (raw.get(eid) or {}).get("metadata", {})
        if e["source"] == "internal:relationship_history" and e["approval_status"] == "approved" \
                and org and e["customer_org_id"] == org:
            docs.setdefault(e["document_id"], []).append({**e, "doc_type": meta.get("doc_type")})
    for doc, passages in sorted(docs.items()):
        kind = passages[0]["doc_type"]
        text = " ".join(raw[p["evidence_id"]]["text"] for p in passages)
        ids = [p["evidence_id"] for p in passages]
        nums = figures(" ".join(raw[p["evidence_id"]]["text"] for p in passages
                                if not re.match(r"\s*(Subject|From|Date):", raw[p["evidence_id"]]["text"])))
        if kind == "correspondence":
            topics.append(_topic(f"customer_request:{doc}", "our_relationship",
                                 "State what the customer asked for (with the message date), any reply or commitment "
                                 "made and its recorded status.", [ids],
                                 _num_markers(nums) or _word_markers(terms(text, exclude=name_words))))
        elif kind == "proposal":
            topics.append(_topic(f"proposal_terms:{doc}", "our_relationship",
                                 "State the proposed product, quantity, price, validity date, when it was sent and its "
                                 "recorded status.", [ids], _num_markers(nums)))
        else:
            topics.append(_topic(f"customer_record:{doc}", "our_relationship",
                                 "State the recorded decisions, commitments and status.", [ids],
                                 _num_markers(nums) or _word_markers(terms(text, exclude=name_words))))

    # Approved meeting records: concerns and decisions, and every unresolved task.
    for eid, e in index.items():
        record = (raw.get(eid) or {}).get("record")
        if e["source"] != "internal:meeting_history" or not record:
            continue
        said = " ".join(record.get("concerns", []) + record.get("decisions", []))
        if said.strip():
            topics.append(_topic(f"meeting_record:{eid}", "our_relationship",
                                 "State the recorded concerns and decisions of this meeting.", [[eid]],
                                 _word_markers(terms(said, exclude=name_words))))
        for n, t in enumerate(record.get("follow_up_tasks", [])):
            if t["status"] == "Completed":
                continue
            topics.append(_topic(f"open_task:{eid}:{n}", "our_relationship",
                                 f"State the unresolved task '{t['description']}' with its status ({t['status']}) and "
                                 f"due date ({t['due_date']}).", [[eid]],
                                 _word_markers(terms(t["description"], 6, exclude=name_words))))

    # Pricing in play (negotiation, follow-up) and approval policy (negotiation).
    if purpose in ("negotiation", "follow_up"):
        for eid, e in index.items():
            if reasons.get(eid, "").startswith("price_row_in_play:"):
                product, tier = row_product(raw[eid]["text"])
                price = re.search(r"List price \(USD\):\s*([\d.,]+)", raw[eid]["text"])
                # In a recommendation, not under opportunities: existing proposal terms are not an opportunity.
                # I6: once, in the analysis item that compares it (no restatement in a recommendation).
                topics.append(_topic(f"list_price:{eid}", "our_relationship" if layout else "meeting_recommendations",
                                     f"State the current list price of {product} ({tier}) once, in an analysis item "
                                     "beside the proposed or requested terms (usually the price position in "
                                     "our_relationship or the requested addition in opportunities); do not repeat it "
                                     "in a recommendation." if layout else
                                     f"In a recommendation, state the current list price of {product} ({tier}) beside "
                                     "the proposed or requested terms.", [[eid]],
                                     _num_markers([price.group(1)] if price else [])))
    if purpose == "negotiation":
        policy = [eid for eid in index if reasons.get(eid, "").startswith("purpose_document:negotiation:")
                  and re.search(r"discount", raw[eid]["text"], re.I)]
        if policy:
            topics.append(_topic("approval_policy", "meeting_recommendations",
                                 "State the discount-approval thresholds that govern any concession in this "
                                 "negotiation.", [policy], _num_markers(figures(" ".join(raw[i]["text"]
                                                                                         for i in policy)))))

    # D1 (owner-approved 2026-11-18): a discount or commercial-terms request in the customer's approved records, with
    # the policy retrieved for it, requires the approval authority and conditions to be stated (any purpose).
    _approval_requirement(bundle, topics, raw, reasons, purpose)

    # Product demonstration: every capability area the selected product and security evidence documents.
    if purpose == "product_demo":
        demo = [eid for eid in index if reasons.get(eid, "").startswith("purpose_document:product_demo:")]
        for area, pattern in DEMO_AREAS.items():
            ids = [eid for eid in demo if re.search(pattern, raw[eid]["text"], re.I)]
            if not ids:
                continue
            if area == "document_control":  # every documented core capability, each stated (validation correction)
                text = " ".join(raw[i]["text"] for i in ids)
                caps = [(label, said) for label, documented, said in DOCUMENT_CONTROL
                        if re.search(documented, text, re.I)]
                listed = ", ".join(label for label, _ in caps)
                topics.append({**_topic(f"demo:{area}", "meeting_recommendations" if layout else "opportunities",
                                        f"In the demonstration plan, show the core document control this evidence "
                                        f"documents, naming each capability: {listed}. Keep it separate from approval "
                                        "workflows and say why it may matter to this organization (to verify, not "
                                        "assumed).", [ids], [said for _, said in caps]),
                               "require_all": True, "labels": [label for label, _ in caps], "no_gap": True})
                continue
            topics.append(_topic(f"demo:{area}", "meeting_recommendations" if layout else "opportunities",
                                 f"In the demonstration plan, one recommendation for {area.replace('_', ' ')}: what "
                                 "to show from this evidence and why it may matter to this organization (to verify, "
                                 "not assumed)." if layout else
                                 f"Explain what can be demonstrated for {area.replace('_', ' ')} from this evidence "
                                 "and why it may matter to this organization (to verify, not assumed).",
                                 [ids], [pattern]))

    # Introduction, and a general meeting with a new lead (validation correction): fit hypotheses linking product
    # evidence to the organization's own evidence. The new-lead general meeting has product descriptions only when
    # selection found no customer records (selection.context_documents).
    if purpose in ("introduction", "general"):
        product_ids = [eid for eid in index if reasons.get(eid, "").startswith(f"purpose_document:{purpose}:")]
        company_ids = [eid for eid, e in index.items()
                       if e["source"] in ("internal:company_profile", "external_news")]
        capability = terms(" ".join(raw[i]["text"] for i in product_ids), exclude=name_words)
        if product_ids and company_ids:
            topics.append(_topic("fit_hypotheses", "opportunities",
                                 "Connect at least one documented product capability to a plausible need suggested by "
                                 "the organization's own evidence or news, labelled as a hypothesis to verify. Cite "
                                 "both the product evidence and the organization's evidence.",
                                 [product_ids, company_ids], _word_markers(capability)))

    # I7 (owner-approved 2026-11-16): the organization's identity and material, dated developments from its own
    # official documents, and neutral discovery questions about what the evidence does not establish.
    from deal_prep import company_context
    topics += company_context.company_topics(bundle, index) + company_context.discovery_topics(bundle, index)

    # Contested figures (evidence profile): both sides, attributed, unresolved.
    prof = profile(list(index.values()), (bundle.get("identity") or {}).get("domain"))
    seen = set()
    for eid, p in sorted(prof.items()):
        for other in p.get("contested_with", []):
            key = frozenset({document_key(index[eid]), document_key(index[other])})  # a web result has no document ID
            if key in seen:
                continue
            seen.add(key)
            sides = [[i for i, q in prof.items() if document_key(index[i]) == d and q.get("contested_with")]
                     for d in sorted(key)]
            nums = figures(" ".join(index[i]["excerpt"] for s in sides for i in s))
            topics.append(_topic(f"contested:{len(seen)}", "company_overview",
                                 "These sources state different figures for the same thing: give both, attributed to "
                                 "their sources, and say the figure is unresolved.", sides, _num_markers(nums)))

    topics = topics[:MAX_TOPICS]
    # C2: every other purpose's compact company essentials, after the cap so they never displace a topic above.
    topics += company_context.brief_topics(bundle, index)
    # I4: chronological ambiguities (both sides together) and undated history (marked if used).
    if chronology.ENABLED:
        entries = list(index.values())
        for n, c in enumerate(c for c in chronology.derived_conflicts(entries, (bundle.get("identity") or {})
                                                                       .get("domain"))
                              if c["kind"] == "chronological_ambiguity"):
            topics.append(_topic(f"chronology:{n + 1}", "company_overview",
                                 f"A state dated {c['state_year']} and a decision about the same subject dated "
                                 f"{c['decision_year']} do not establish how they relate: give both, attributed and "
                                 "cited together, say the relationship is unclear, and do not call them consistent "
                                 "or contradictory.", [[s["evidence_id"]] for s in c["sides"]],
                                 _num_markers([str(c["state_year"]), str(c["decision_year"])])))
        for eid, e in index.items():
            if chronology.undated_history(e):
                topics.append({**_topic(f"undated:{eid}", "company_overview",
                                        "This historical statement gives no date. If you use it, say 'date not "
                                        "stated'; never add a date.", [[eid]], [r"date not stated|undated|no date"]),
                               "conditional": True})
    topics += company_context.undated_topics(index)  # I7: anything used from an undated page says so
    if analysis is not None:  # I5: findings of the deterministic business analysis
        topics += business_topics(analysis, layout)
    return topics


_VERIFY = [r"verif|confirm|check|clarif|not (?:stated|recorded|available|in the evidence)|cannot be calculated|unclear"]
_URGENT = r"tomorrow|today|overdue|urgent|imminent|this week|\b{days} days?\b|within (?:a|one|\d+) (?:days?|week)"


def _figure_markers(*values: float) -> list[str]:
    """Markers for a calculated figure in its usual written forms (52, 52.00, 1,920, 1920, 5.8, 5.77)."""
    forms = set()
    for v in values:
        for f in (f"{v:,.2f}", f"{v:.2f}", f"{v:,.1f}", f"{v:.1f}", f"{v:,.0f}" if float(v).is_integer() else None,
                  f"{v:.0f}" if float(v).is_integer() else None):
            if f:
                forms.add(f[:-3] if f.endswith(".00") else f)
    return [rf"(?<![\d.,]){re.escape(f)}(?![\d])" for f in sorted(forms)]


_ONCE = (" State this once, here; a recommendation acts on it without restating the figures, except a threshold or date "
         "the action depends on.")


def business_topics(a: dict, layout: bool = False) -> list[dict]:
    """I5: what the briefing must say about the business analysis: each price position with its approval tier, each
    requested addition's list-price cost, urgent deadlines, status disagreements, what must be verified, and (if
    used) eligibility limits of product capabilities. layout (I6): one home per result; capabilities limited to
    another product are not pitched without supporting evidence."""
    from deal_prep.business import money
    once = _ONCE if layout else ""
    topics = []
    for p in a["price_positions"]:
        if p["status"] == "calculated":
            ap = p.get("approval", {})
            # Validation correction (2026-11-14): purpose-neutral wording, since the approval policy now also reaches
            # meetings that are not negotiations (it used to say "for the negotiation").
            topics.append(_topic(
                p["id"], "our_relationship",
                f"As analysis (an inference or a recommendation, never a fact): the proposed "
                f"{money(p['proposed_price'], p['currency'])} is {p['discount_display']} below the current list price "
                f"of {money(p['list_price'], p['currency'])} {p['unit']}. {ap.get('text', '')} Say what this means for "
                f"this meeting without suggesting a concession the customer has not asked for; the proposal is an "
                f"offer, not an agreed price.{once}",
                [[p["proposal_evidence_id"]], [p["list_evidence_id"]]],
                _figure_markers(p["discount_pct"], round(p["discount_pct"], 1))))
        else:
            topics.append(_topic(p["id"], "our_relationship",
                                 f"The price position cannot be calculated: {p['reason']} Say what must be verified; "
                                 f"do not estimate it.", [[p["proposal_evidence_id"]]], _VERIFY))
    for r in a["requested_additions"]:
        if r["status"] == "calculated":
            # An addition to an existing proposal is discussed with that proposal (our_relationship): existing
            # proposal terms are not an opportunity. A new item the customer asked for is an opportunity.
            extends = "quantity_after_addition" in r
            # I6: say where a new add-on goes as plainly as where an extension goes (B1: both were put with the
            # proposal, leaving Opportunities empty).
            where = (" in our_relationship (it extends the existing proposal)" if extends else
                     " in opportunities (the existing proposal does not include it, so it is an opportunity, not an "
                     "existing term)" if layout else "")
            topics.append(_topic(
                r["id"], "our_relationship" if extends else "opportunities",
                f"As analysis{where}: the "
                f"customer's request for {r['quantity']:g} {r['unit']} of {r['product']} costs {r['display']}. Cite "
                f"the request and the list price; say it is a list-price cost, not a quote."
                + (" It is a request that has not been quoted, not part of the existing terms." if layout and extends
                   else " Do not cite the proposal in this item." if layout else "") + once,
                [[r["request_evidence_id"]], [r["list_evidence_id"]]],
                _figure_markers(r.get("monthly_at_list", r.get("total_at_list", 0)))))
        else:
            topics.append(_topic(r["id"], "meeting_recommendations",
                                 f"{r.get('minimum_term_check', '')} {r['reason']} Say what must be clarified or "
                                 f"verified; do not estimate a price.".strip(), [[r["request_evidence_id"]]], _VERIFY))
    for d in a["deadlines"]:
        if d.get("urgency") in ("overdue", "due today", "due tomorrow", "due within 7 days"):
            topics.append(_topic(f"urgent:{d['id']}", "meeting_recommendations",
                                 f"Flag the urgency: {d['text']}", [d["evidence_ids"][:1]],
                                 [_URGENT.format(days=abs(d["days_left"]))]))
    for s in a["status_checks"]:
        topics.append(_topic(s["id"], "meeting_recommendations",
                             f"Records disagree: {s['text']} Cite both records and say what to verify."
                             + (" Explain the disagreement once, in this recommendation; elsewhere state each record "
                                "without repeating the explanation." if layout else ""),
                             [[s["task_evidence_id"]], s["correspondence_evidence_ids"]], _VERIFY))
    for e in a["eligibility"]:
        # Correction (a), owner-approved 2026-11-14: the limit in the source's own terms ("the Business tier adds it");
        # "only" only when the source says so.
        limit = e.get("limit") or f"it is available to {e['available_to']} only"
        if layout and e["available_to"].endswith(" customers"):  # I6: a capability of another product
            need = (f"Eligibility: '{e['capability']}' Do not recommend, pitch or plan to demonstrate it unless this "
                    f"organization's own evidence supports {e['marker']}; if you mention it, present it as a "
                    f"hypothesis to verify and say in the same item that {limit}.")
        else:
            need = (f"Eligibility: '{e['capability']}' Whenever you mention this capability, say in the same item that "
                    f"{limit}.")
        topics.append({**_topic(e["id"], "opportunities", need, [[e["evidence_id"]]],
                                [rf"\b{re.escape(e['marker'])}\b"]),
                       "conditional": True, "triggers": [rf"\b{re.escape(w)}" for w in e["triggers"]]})
    return topics


def model_contract(bundle: dict, topics: list[dict], layout: bool = False) -> dict:
    """What the drafter sees: the purpose brief and each topic's id, section, requirement and evidence IDs."""
    brief = PURPOSE_BRIEFS.get(bundle.get("purpose"), PURPOSE_BRIEFS["general"])
    if layout and bundle.get("purpose") in LAYOUT_BRIEFS:  # I6
        brief += " " + LAYOUT_BRIEFS[bundle["purpose"]]
    if bundle.get("purpose") == "general" and any(t["id"] == "fit_hypotheses" for t in topics):  # new lead
        brief += " " + NEW_LEAD_GENERAL_BRIEF
    if any(t["id"].startswith("company:") and t["id"] != "company:brief" for t in topics):  # I7
        brief += " " + COMPANY_CONTEXT_BRIEF
    elif any(t["id"] == "company:brief" for t in topics):  # C2: the relationship and commercial items come first
        brief += " " + COMPANY_BRIEF_NOTE
    return {"purpose_brief": brief,
            "essential_topics": [{"id": t["id"], "section": t["section"], "requirement": t["requirement"],
                                  "evidence_ids": sorted({i for g in t["groups"] for i in g})} for t in topics]}


def coverage(draft: dict, topics: list[dict]) -> dict:
    """Classify every essential topic against the final briefing (see the module docstring)."""
    items = [it for its in draft["sections"].values() for it in its]
    declared = {d["id"] for d in draft.get("disclosures", [])}
    out, missing_caps = {}, {}
    for t in topics:
        # I7: a topic without evidence (a discovery question) counts only in its home section.
        pool = draft["sections"].get(t["section"], []) if t.get("home_only") else items
        if t.get("require_all"):  # validation correction: EVERY marker stated by the items citing the evidence
            citing = [it for it in pool if all(set(it["evidence_ids"]) & set(g) for g in t["groups"])]
            absent = [label for label, m in zip(t.get("labels", t["markers"]), t["markers"])
                      if not any(re.search(m, it["text"], re.I) for it in citing)]
            status = "missing" if not citing else "cited_only" if absent else "communicated"
            if status != "communicated" and not t.get("no_gap") and f"topic_gap:{t['id']}" in declared:
                status = "gap_declared"
            if absent:
                missing_caps[t["id"]] = absent
            out[t["id"]] = status
            continue
        if t.get("conditional"):  # I4/I5: required only if used: every item using it must carry the marker
            using = [it for it in pool if set(it["evidence_ids"]) & set(t["groups"][0])
                     and (not t.get("triggers") or any(re.search(w, it["text"], re.I) for w in t["triggers"]))]
            out[t["id"]] = ("not_used" if not using else "communicated"
                            if all(any(re.search(m, it["text"], re.I) for m in t["markers"]) for it in using)
                            else "cited_only")
            continue
        status = "missing"
        for it in pool:
            ids = set(it["evidence_ids"])
            if not all(ids & set(g) for g in t["groups"]):
                continue
            if not t["markers"] or any(re.search(m, it["text"], re.I) for m in t["markers"]):
                status = "communicated"
                break
            status = "cited_only"
        if status != "communicated" and f"topic_gap:{t['id']}" in declared:
            status = "gap_declared"
        out[t["id"]] = status
    essential = {t["id"] for t in topics if not t.get("conditional")}
    counts = {s: sum(v == s for k, v in out.items() if k in essential)
              for s in ("communicated", "cited_only", "gap_declared", "missing")}

    def conditional(prefix):
        part = {k: v for k, v in out.items() if k not in essential and k.startswith(prefix)}
        return {s: sum(v == s for v in part.values()) for s in ("communicated", "cited_only", "not_used")}
    return {"topics": out, "counts": counts, "total": len(essential), "undated": conditional("undated:"),
            "eligibility": conditional("eligibility:"), "missing_capabilities": missing_caps}


# C1: a figure problem (untraced, calculated as fact, or mismatched) weighs more than one lost topic or verified figure,
# so a repair that fixes a genuinely unsupported figure is still accepted, while a repair that only trades a verified
# figure for a topic is not (briefing._repair counts the losses).
FIGURE_PROBLEM_WEIGHT = 2


def figure_problems(cov: dict) -> int:
    figs = cov.get("figures") or {}
    return sum(len(figs.get(k, [])) for k in ("untraced", "calculated_in_fact", "mismatched"))


def score(cov: dict) -> int:
    """Topics communicated, conditional ones correctly handled, minus figure problems (used to accept a repair)."""
    return (cov["counts"]["communicated"] + cov.get("undated", {}).get("communicated", 0)
            + cov.get("eligibility", {}).get("communicated", 0) - FIGURE_PROBLEM_WEIGHT * figure_problems(cov))


def unmet(cov: dict) -> list[str]:
    return [tid for tid, s in cov["topics"].items() if s in ("cited_only", "missing")]
