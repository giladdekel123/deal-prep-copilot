"""C2.4 (owner decision 2026-11-17): every briefing carries purpose-sensitive company essentials. Introductions and
general meetings get the full set (identity, latest material developments, ownership, leadership, outlook); follow-up,
negotiation and product-demonstration briefings get ONE compact company:brief, added after the topic cap so it never
displaces a relationship or commercial topic, worded to keep those first and, in a negotiation, never to infer the
customer's budget or stance from its public results. Without company evidence, nothing is invented: the limitation is
disclosed. Invented companies only."""
from datetime import date, timedelta

import pytest

from deal_prep import company_context as cc, contract
from deal_prep.disclosures import required_disclosures

TODAY = date(2026, 11, 15)


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def doc(doc_id, published, quotes, title="release"):
    label = (f"PUBLIC SOURCE · Acme Corp · https://acme.example/{doc_id.lower()} · published {published} · retrieved "
             f"2026-11-15 · verification primary")
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": published,
            "approval_status": "approved"}
    out = [{"evidence_id": f"{doc_id}#0", "info_origin": "public_source", "document_id": doc_id, "metadata": meta,
            "provenance_label": label,
            "text": f"PUBLIC SOURCE — Acme Corp: {title} - **Publication date:** {published}"}]
    return out + [{"evidence_id": f"{doc_id}#{n}", "info_origin": "public_source", "document_id": doc_id,
                   "metadata": meta, "provenance_label": label, "text": f'Excerpts > [E{n}] "{q}"'}
                  for n, q in enumerate(quotes, 1)]


ABOUT = doc("ACME-ABOUT", "unknown", ["Acme Corp is a global supplier of industrial valves, and we operate in 12 "
                                      "countries."], title="about us")
Q3 = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1,569.7 million, up 10.1% year-on-year.",
                              "Profit for the period was EUR 140.2 million, down 12%, mainly due to restructuring."],
         title="interim report, third quarter 2026")


def bundle(entries, purpose):
    return {"purpose": purpose, "created_at": "2026-11-15T10:00:00+00:00", "status": "complete",
            "company_input": "Acme Corp",
            "identity": {"name": "Acme Corp", "org_id": "acme", "domain": "acme.example", "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": list(entries)}},
            "external": {"status": "fallback_30d_found", "evidence": []}, "selection": {},
            "gaps": ["No prior relationship records (proposals, meetings, correspondence) with Acme Corp."]}


def company_ids(b):
    return [t["id"] for t in contract.essential_topics(b) if t["id"].startswith(("company:", "discovery:"))]


@pytest.mark.parametrize("purpose", ["introduction", "general"])
def test_introductions_and_general_meetings_get_the_full_company_essentials(purpose):
    ids = company_ids(bundle(ABOUT + Q3, purpose))
    assert {"company:identity", "company:latest_release"} <= set(ids) and "company:brief" not in ids


@pytest.mark.parametrize("purpose", ["follow_up", "negotiation", "product_demo"])
def test_other_purposes_get_exactly_one_compact_company_brief(purpose):
    topics = {t["id"]: t for t in contract.essential_topics(bundle(ABOUT + Q3, purpose))}
    assert [t for t in topics if t.startswith(("company:", "discovery:"))] == ["company:brief"]
    brief = topics["company:brief"]
    assert brief["section"] == "company_overview" and brief["require_all"]
    assert {"ACME-ABOUT#1", "ACME-Q3#2"} <= set(brief["groups"][0])  # who it is; the headline result (profit)
    assert "one or two items" in brief["requirement"] and "come first" in brief["requirement"]


def test_the_negotiation_brief_forbids_inferring_budget_priorities_or_stance():
    brief = {t["id"]: t for t in contract.essential_topics(bundle(ABOUT + Q3, "negotiation"))}["company:brief"]
    for words in ("budget", "cost pressure", "commercial priorities", "negotiating stance", "never infer"):
        assert words in brief["requirement"]
    follow = {t["id"]: t for t in contract.essential_topics(bundle(ABOUT + Q3, "follow_up"))}["company:brief"]
    assert "relationship history and open commitments come first" in follow["requirement"]


def test_the_brief_is_outside_the_topic_cap_and_never_displaces_another_topic(monkeypatch):
    monkeypatch.setattr(contract, "MAX_TOPICS", 0)  # every capped topic is cut ...
    assert "company:brief" in company_ids(bundle(ABOUT + Q3, "negotiation"))  # ... the brief is not one of them


def test_the_contract_keeps_the_relationship_first_when_only_the_brief_is_present():
    b = bundle(ABOUT + Q3, "negotiation")
    brief = contract.model_contract(b, contract.essential_topics(b))["purpose_brief"]
    assert contract.COMPANY_BRIEF_NOTE in brief and contract.COMPANY_CONTEXT_BRIEF not in brief
    b = bundle(ABOUT + Q3, "introduction")
    assert contract.COMPANY_CONTEXT_BRIEF in contract.model_contract(b, contract.essential_topics(b))["purpose_brief"]


def test_without_company_evidence_nothing_is_invented_and_the_limitation_is_disclosed():
    b = bundle([], "negotiation")
    assert company_ids(b) == []
    gap = next(d for d in required_disclosures(b) if d["id"] == "unknown:business")
    assert "recent official results or announcements" in gap["text"]
    assert not [d for d in required_disclosures(bundle(ABOUT + Q3, "negotiation")) if d["id"] == "unknown:business"]


def fact(text, ids):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": "real_world_fact"}


def test_the_brief_counts_only_when_the_development_and_its_date_are_stated():
    b = bundle(ABOUT + Q3, "follow_up")
    topic = [t for t in contract.essential_topics(b) if t["id"] == "company:brief"]
    vague = {"sections": {"company_overview": [fact("Acme Corp is a global supplier of industrial valves; its latest "
                                                    "interim report shows lower profit.",
                                                    ["ACME-ABOUT#1", "ACME-Q3#2"])]}, "disclosures": []}
    full = {"sections": {"company_overview": [fact(
        f"Acme Corp, a global supplier of industrial valves (page undated), reported profit of EUR 140.2 million for the "
        f"third quarter of 2026, down 12% mainly due to restructuring (interim report, {TODAY.day - 10} November 2026).",
        ["ACME-ABOUT#1", "ACME-Q3#0", "ACME-Q3#2"])]}, "disclosures": []}
    assert contract.coverage(vague, topic)["topics"]["company:brief"] == "cited_only"
    assert contract.coverage(full, topic)["topics"]["company:brief"] == "communicated"


def test_a_recent_document_with_nothing_material_still_discloses_the_limitation():
    """Dated statements in the window but none a result, update, development or figure: no development to state, so
    the follow-up or negotiation briefing discloses it (and its brief, if any, states only who the organization is)."""
    b = bundle(ABOUT + doc("ACME-NOTE", ago(5), ["International demand remains strong."], title="statement"), "follow_up")
    assert not cc.developments(cc.analyse(b)).get("chosen")
    assert [d for d in required_disclosures(b) if d["id"] == "unknown:business"]
