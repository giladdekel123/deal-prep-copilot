"""Mandatory research for one briefing, in deterministic Python (Prompt 04 step 1).

Order, owned entirely by code (no LLM, no agent):
1. Resolve the company. An ambiguous name stops here and asks for clarification.
2. Mandatory internal RAG: a fixed set of company-scoped and vendor-wide searches over dms_kb_v1.
   Relationship searches are restricted to synthetic records tied to that company (spec FR-07);
   company-profile searches are restricted to public sources about that company.
   I3 (selection.py): the customer's approved records are then included whole, vendor evidence is chosen for the
   meeting purpose and the products in play, and unrelated price rows and competitor material are left out, each
   with a recorded reason.
3. Mandatory external news search: 48 hours, then 30-day fallback (web_research).
4. Classify completeness: complete / external_with_internal_gap / partial_internal_only /
   insufficient_sources, with explicit gaps. Nothing is skipped or invented.
Internal evidence is never sent to the web provider; the news query is built from the
company name only. The one LLM call and the bounded agent (later steps) consume this bundle.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

from deal_prep import config, web_research
from deal_prep.kb_index import document_passages, load_manifest, search
from deal_prep.provenance import load_registry
from deal_prep.selection import select_competition, select_for_purpose

MEETING_PURPOSES = {"general", "introduction", "product_demo", "negotiation", "follow_up"}
EXTERNAL_OK = {"found_48h", "fallback_30d_found", "not_found"}  # not_found is a completed search
NEWS_PROBLEM = {"provider_error": "The news search could not be completed",
                "budget_exhausted": "The news search was stopped by the usage limit"}
# Owner decision, 8 November 2026: disclosed whenever no curated company profile was retrieved (any company, any
# mode). It does not say that no other information exists, and it does not stop facts backed by other sources.
PROFILE_GAP = ("No curated public company profile was retrieved for this briefing. Company information may be "
               "incomplete; any facts included must be supported by other cited sources.")


def _internal_topics(identity) -> list[dict]:
    """Fixed mandatory internal searches. Queries are internal only; never sent to Tavily."""
    name, org = identity.name, identity.org_id
    topics = [
        {"topic": "vendor_products_pricing", "sections": ["opportunities", "meeting_recommendations"],
         "query": "Nivarque products, tiers and current list prices", "scope": "global",
         "origin": "synthetic_record"},
        {"topic": "competition", "sections": ["competitive_positioning"],
         "query": "competitor battlecard positioning and price objections", "scope": "global",
         "origin": "synthetic_record", "doc_types": {"battlecard"}},
    ]
    if org:
        topics += [
            {"topic": "company_profile", "sections": ["company_overview"],
             "query": f"{name} company profile, history and ownership", "scope": "company",
             "origin": "public_source"},
            {"topic": "relationship_history", "sections": ["our_relationship", "opportunities"],
             "query": f"proposals, meetings, correspondence and prices with {name}", "scope": "company",
             "origin": "synthetic_record", "customer_only": True},
        ]
    return topics


def _run_internal(topic, identity, k, chroma_dir):
    started = time.monotonic()
    if topic["scope"] == "global":
        wide = k * 4 if topic.get("doc_types") else k  # widen, then keep only the topic's document types
        results = search(topic["query"], k=wide, global_only=True, origin=topic["origin"], chroma_dir=chroma_dir)
        if topic.get("doc_types"):
            results = [e for e in results if e["metadata"]["doc_type"] in topic["doc_types"]][:k]
    else:
        from deal_prep import company_context
        from deal_prep.kb_index import CANDIDATES
        # I7: the company profile is read across documents (one passage per document, plus the newest dated ones),
        # not as the top k passages, which can all come from one page.
        diverse = company_context.ENABLED and topic["topic"] == "company_profile"
        results = search(topic["query"], k=CANDIDATES if diverse else k * 2 if topic.get("customer_only") else k,
                         company_id=identity.org_id, origin=topic["origin"], chroma_dir=chroma_dir)
        if topic.get("customer_only"):
            results = [e for e in results if e["metadata"]["customer_org_id"] == identity.org_id][:k]
        elif diverse:
            results = company_context.profile_passages(
                [e for e in results if e["metadata"]["subject_org_id"] == identity.org_id], identity.org_id,
                chroma_dir)
        else:
            results = [e for e in results if e["metadata"]["subject_org_id"] == identity.org_id][:k]
    trace = {"stage": "internal_rag", "topic": topic["topic"], "scope": topic["scope"],
             "origin_filter": topic["origin"], "results": len(results),
             "evidence_ids": [e["evidence_id"] for e in results],
             "elapsed_ms": round((time.monotonic() - started) * 1000), "outcome": "ok"}
    return results, trace


def add_comparison_sources(bundle: dict, chroma_dir) -> None:
    """I2: when a retrieved public passage states a figure, make sure every public document already retrieved for
    this company contributes its own verbatim statement of the same figure, so a disagreement (or a mere copy) is
    visible instead of hidden, and an official verbatim passage is available instead of only its summary. Only
    documents with a retrieved passage are looked at, by document ID (no new search)."""
    from deal_prep import evidence_profile as ep
    from deal_prep.evidence import kb_evidence, normalize

    block = bundle.get("internal", {}).get("company_profile")
    if not block:
        return
    have = kb_evidence(bundle)
    have_ids = {e["evidence_id"] for e in have}
    shown = [normalize(e, "internal:company_profile") for e in have if e["info_origin"] == "public_source"]
    frames = {ep._frame(s) for e in shown for s in ep.statements(ep.claims_as_text(e["excerpt"]))}
    if not frames:
        return
    started, added = time.monotonic(), []
    for doc_id in sorted({e["document_id"] for e in have if e["info_origin"] == "public_source"}):
        for p in document_passages(doc_id, chroma_dir):
            n = normalize(p, "internal:company_profile")
            if p["evidence_id"] in have_ids or ep.statement_form(n) != "verbatim_excerpt":
                continue
            if any(ep._frame(s) in frames for s in ep.statements(n["excerpt"])):
                added.append(p)
                have_ids.add(p["evidence_id"])
    if added:
        block["evidence"].extend(added)
        bundle["trace"].append({"stage": "comparison_sources", "results": len(added),
                                "evidence_ids": [e["evidence_id"] for e in added],
                                "elapsed_ms": round((time.monotonic() - started) * 1000), "outcome": "ok"})


def add_conflict_sources(bundle: dict, chroma_dir, now: datetime) -> None:
    """For each disclosed (unresolved) conflict, make sure the exact passage containing each side's
    conflict_statement is in the bundle, so the disclosure can cite the passage it quotes. Passages
    the searches did not retrieve are fetched from the local index by document ID (no ranking).
    Called after the mandatory searches and again after the agent (which may surface new conflicts)."""
    from deal_prep.disclosures import passage_with, unresolved_conflicts
    from deal_prep.evidence import kb_evidence

    started = time.monotonic()
    manifest = {d["document_id"]: d for d in load_manifest()}
    have = kb_evidence(bundle)
    # A conflict is relevant when a retrieved passage states one of its sides (contains that document's
    # conflict_statement), or when both sides were already retrieved. Detection must not depend on
    # both sides happening to rank in the top results.
    groups = set(unresolved_conflicts(bundle, now.date()))
    for e in have:
        doc = manifest.get(e["document_id"], {})
        if doc.get("conflict_group") and passage_with([e], e["document_id"], doc.get("conflict_statement")):
            groups.add(doc["conflict_group"])
    added = []
    for g in sorted(groups):
        for doc_id in sorted(d for d, doc in manifest.items() if doc.get("conflict_group") == g):
            statement = manifest[doc_id].get("conflict_statement")
            if not statement or passage_with(have + added, doc_id, statement):
                continue
            found = passage_with(document_passages(doc_id, chroma_dir), doc_id, statement)
            if found:
                added.append(found)
    if added:
        bundle.setdefault("conflict_sources", []).extend(added)
        bundle["trace"].append({"stage": "conflict_sources", "results": len(added),
                                "evidence_ids": [e["evidence_id"] for e in added],
                                "elapsed_ms": round((time.monotonic() - started) * 1000), "outcome": "ok"})
    # D2: the statement passages of conflicts set aside as irrelevant are kept in reserve, outside the drafting input,
    # so that if the briefing turns out to be about one of them, both sides can be quoted from the passages that
    # state them (disclosures.mentioned_conflicts). They are not evidence the model sees.
    from deal_prep.disclosures import set_aside_conflicts
    reserve = []
    for g, docs in sorted(set_aside_conflicts(bundle, now.date()).items()):
        for doc_id in docs:
            found = passage_with(document_passages(doc_id, chroma_dir), doc_id,
                                 manifest.get(doc_id, {}).get("conflict_statement"))
            if found and found["evidence_id"] not in {e["evidence_id"] for e in reserve}:
                reserve.append(found)
    bundle["conflict_reserve"] = reserve


def gather_research(company_name: str, *, news_client, budget, domain: str | None = None,
                    purpose: str = "general", k: int = 5, chroma_dir: Path = config.CHROMA_DIR,
                    now: datetime | None = None, history_search=None) -> dict:
    """history_search(identity) -> approved meeting-record evidence for that company (Stage 2), or None."""
    now = now or datetime.now(timezone.utc)
    if not company_name or not company_name.strip():
        raise ValueError("company name is required")
    if purpose not in MEETING_PURPOSES:
        raise ValueError(f"meeting purpose must be one of {sorted(MEETING_PURPOSES)}")

    ident = web_research.identify_company(company_name, domain=domain)
    bundle = {"company_input": company_name, "purpose": purpose, "created_at": now.isoformat(),
              "identity_status": ident["status"], "candidates": ident["candidates"], "identity": None,
              "internal": {}, "external": None, "gaps": [], "trace": [],
              "mandatory": {"internal_rag": False, "external_news": False}}
    if ident["status"] == "clarification_required":
        bundle["status"] = "clarification_required"
        registry = load_registry()
        names = " and ".join(registry[c]["name"] for c in ident["candidates"])
        bundle["gaps"].append(f"'{company_name}' could refer to more than one organization ({names}). "
                              "Please give the official website domain or a more specific name. No research was run.")
        return bundle

    identity = ident["identity"]
    bundle["identity"] = {"name": identity.name, "org_id": identity.org_id, "domain": identity.domain,
                          "country": identity.country, "confidence": identity.confidence}

    # Mandatory internal RAG
    for topic in _internal_topics(identity):
        results, trace = _run_internal(topic, identity, k, chroma_dir)
        bundle["internal"][topic["topic"]] = {"sections": topic["sections"], "evidence": results}
        bundle["trace"].append(trace)
    bundle["mandatory"]["internal_rag"] = True

    if history_search is not None:  # approved Stage 2 meeting records only (SQLite-authoritative)
        started = time.monotonic()
        history = history_search(bundle["identity"])
        bundle["internal"]["meeting_history"] = {"sections": ["our_relationship"], "evidence": history}
        bundle["trace"].append({"stage": "internal_rag", "topic": "meeting_history", "scope": "company",
                                "origin_filter": "synthetic_record", "results": len(history),
                                "evidence_ids": [e["evidence_id"] for e in history],
                                "elapsed_ms": round((time.monotonic() - started) * 1000), "outcome": "ok"})

    select_for_purpose(bundle, chroma_dir, now.date())  # I3: customer records whole; purpose-aware vendor evidence
    add_conflict_sources(bundle, chroma_dir, now)
    add_comparison_sources(bundle, chroma_dir)

    company_specific = sum(len(bundle["internal"].get(t, {}).get("evidence", []))
                           for t in ("company_profile", "relationship_history", "meeting_history"))
    no_internal_records = identity.org_id is None and not bundle["internal"].get("meeting_history", {}).get("evidence")
    if not no_internal_records and not bundle["internal"].get("company_profile", {}).get("evidence"):
        bundle["gaps"].append(PROFILE_GAP)  # (the "no internal records" gap below already covers that case)
    if no_internal_records:
        bundle["gaps"].append(f"No internal records for '{identity.name}': the company is not in the "
                              "curated registry, so only vendor-wide documents were searched.")
    elif identity.org_id is None:
        pass  # an unregistered company with approved meeting records has internal history
    elif not (bundle["internal"]["relationship_history"]["evidence"]
              or bundle["internal"].get("meeting_history", {}).get("evidence")):
        bundle["gaps"].append(f"No prior relationship records (proposals, meetings, correspondence) "
                              f"with {identity.name}.")

    # Mandatory external news research
    news = web_research.research_company_news(identity, news_client, budget, now=now)
    bundle["external"] = news
    bundle["mandatory"]["external_news"] = True
    bundle["trace"].extend({"stage": "external_news", **t} for t in news["trace"])
    select_competition(bundle, chroma_dir)  # I3: after the news, which may name a competitor
    if news["status"] == "disabled":
        bundle["gaps"].append(news["message"])  # deliberately not searched; the message says why
    elif news["status"] not in EXTERNAL_OK:
        bundle["gaps"].append(f"{NEWS_PROBLEM.get(news['status'], 'The news search was incomplete')}. "
                              f"{news['message']}")
    elif news["status"] == "not_found":
        bundle["gaps"].append(news["message"])

    external_ok = news["status"] in EXTERNAL_OK
    if not external_ok and company_specific == 0:
        bundle["status"] = "insufficient_sources"  # no speculative briefing (Prompt 04 step 6c)
    elif not external_ok:
        bundle["status"] = "partial_internal_only"  # step 6b
    elif company_specific == 0:
        bundle["status"] = "external_with_internal_gap"  # step 6a
    else:
        bundle["status"] = "complete"
    return bundle
