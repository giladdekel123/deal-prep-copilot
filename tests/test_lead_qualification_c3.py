"""C3 (owner-approved 2026-11-17): qualification questions for early-stage leads. A general lead-state rule, from the
organization's approved records only:
  - new: the research found no relationship records (unchanged: systems, who decides, timing; no budget question);
  - early stage: approved correspondence only (an inquiry, outreach, a reply), with no approved meeting record and no
    approved proposal: at most five neutral qualification questions (current systems and workflows; who decides and
    how approval works; budget or funding status; timing and decision process; scope, security, deployment or
    integration constraints), building on what the correspondence already addresses instead of asking it again;
  - established: an approved meeting record or proposal: no introductory questions.
Draft or superseded records never count. Introductions and general meetings only (as agreed). Invented companies."""
import re

import pytest

from deal_prep import company_context as cc, contract
from deal_prep.disclosures import required_disclosures

NAME = "Halden Build Group"
CREATED = "2026-11-15T10:00:00+00:00"


def record(eid, doc_type, text, status="approved", org="halden"):
    doc = eid.split("#")[0]
    return {"evidence_id": eid, "info_origin": "synthetic_record", "document_id": doc,
            "provenance_label": f"SYNTHETIC RECORD · {doc} · {status}", "text": text, "excerpt": text,
            "metadata": {"doc_type": doc_type, "approval_status": status, "customer_org_id": org,
                         "document_id": doc}}


INQUIRY = [record("COR-7#0", "correspondence", "Subject: Website inquiry about controlled drawings"),
           record("COR-7#1", "correspondence", "Inquiry from the document control lead: options for controlled "
                                               "drawings with review workflows, about 120 users. Can documents be "
                                               "hosted in Canada? We are reviewing options for next financial year."),
           record("COR-7#2", "correspondence", "Reply from our account executive: an introductory call is proposed "
                                               "for 20 November 2026."),
           record("COR-7#3", "correspondence", "Status: no proposal sent; no other contact recorded.")]
OUTREACH = [record("COR-8#1", "correspondence", "Outreach email to the IT department introducing document control "
                                                "software."),
            record("COR-8#2", "correspondence", "Status: no reply received.")]
MEETING = {"evidence_id": "HIST-MTG-3#1", "info_origin": "synthetic_record", "document_id": "HIST-MTG-3",
           "provenance_label": "SYNTHETIC RECORD · approved meeting record", "text": "Meeting record: scoping call.",
           "excerpt": "Meeting record: scoping call.",
           "metadata": {"doc_type": "meeting_record", "approval_status": "approved", "customer_org_id": "halden"}}
PROPOSAL = record("PRP-4#1", "proposal", "Proposal: 120 users, valid until 31 December 2026.")
DRAFT_NOTE = record("MTG-9#1", "meeting_notes", "Draft notes: the CFO approved the budget, and the IT director "
                                                "decides by March 2027.", status="draft")


def bundle(relationship=(), meetings=(), purpose="introduction", gaps=()):
    return {"purpose": purpose, "created_at": CREATED, "status": "complete", "company_input": NAME,
            "identity": {"name": NAME, "org_id": "halden", "domain": "halden.example", "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": []},
                         "relationship_history": {"sections": ["our_relationship"], "evidence": list(relationship)},
                         "meeting_history": {"sections": ["our_relationship"], "evidence": list(meetings)}},
            "external": {"status": "fallback_30d_found", "evidence": []}, "selection": {}, "gaps": list(gaps)}


NEW = [f"No prior relationship records (proposals, meetings, correspondence) with {NAME}."]


def topics(b):
    return {t["id"]: t for t in contract.essential_topics(b)}


def rec(text, ids=()):
    return {"kind": "recommendation", "text": text, "evidence_ids": list(ids), "claim_type": None}


# --- the lead state --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("b, state", [
    (bundle(gaps=NEW), "new"),
    (bundle(INQUIRY), "early_stage"),
    (bundle(OUTREACH), "early_stage"),
    (bundle(INQUIRY + [DRAFT_NOTE]), "early_stage"),                 # a draft note is never a meeting
    (bundle(INQUIRY, meetings=[MEETING]), "established"),
    (bundle(INQUIRY + [PROPOSAL]), "established"),
    (bundle([record("COR-7#1", "correspondence", "Inquiry.", status="draft")]), ""),  # nothing approved
    (bundle([record("COR-7#1", "correspondence", "Inquiry.", org="other")]), ""),   # another organization's record
])
def test_the_lead_state_comes_from_approved_records_only(b, state):
    assert cc.lead_state(b) == state


# --- early-stage leads get qualification questions -------------------------------------------------------------------

@pytest.mark.parametrize("purpose", ["introduction", "general"])
def test_an_early_stage_lead_with_correspondence_gets_the_qualification_questions(purpose):
    t = topics(bundle(OUTREACH, purpose=purpose))
    assert "discovery:buying_context" not in t
    q = t["discovery:qualification"]
    assert q["section"] == "meeting_recommendations" and q["require_all"] and q["home_only"] and q["no_gap"]
    assert q["labels"] == ["current systems and workflows", "who decides and how approval works",
                           "budget or funding status", "timing and decision process",
                           "scope, security, deployment or integration constraints"]
    for words in ("systems and workflows", "who would evaluate and decide", "how approval works",
                  "whether budget or funding", "never assume", "the timing and the steps of any decision",
                  "security, hosting or deployment, and integration", "at most five"):
        assert words in q["requirement"], words


def test_questions_the_correspondence_already_addresses_are_built_on_not_asked_again():
    q = topics(bundle(INQUIRY))["discovery:qualification"]["requirement"]
    asked, built = q.split("The correspondence already addresses")
    # the inquiry gives a timing (next financial year) and a hosting question and scope: build on them
    assert "timing and decision process (COR-7#1)" in built and "constraints (COR-7#1)" in built
    assert "do not ask it afresh" in built
    assert "the timing and the steps" not in asked and "hosting or deployment" not in asked
    # it says nothing of systems, who decides or budget: those are asked
    assert "systems and workflows" in asked and "who would evaluate and decide" in asked and "budget" in asked
    assert "COR-7#2" not in q and "COR-7#3" not in q  # the reply and the status line address nothing


def test_an_unapproved_draft_note_establishes_no_qualification_fact():
    with_draft = topics(bundle(INQUIRY + [DRAFT_NOTE]))["discovery:qualification"]["requirement"]
    assert with_draft == topics(bundle(INQUIRY))["discovery:qualification"]["requirement"]
    assert "MTG-9" not in with_draft and "whether budget or funding" in with_draft


def test_the_questions_are_neutral_and_invent_nothing():
    for b in (bundle(INQUIRY), bundle(OUTREACH)):
        q = topics(b)["discovery:qualification"]["requirement"]
        assert "do not imply a need, a budget, a decision maker or an intention to buy that the correspondence " \
               "does not state" in q
        assert not re.search(r"\b(?:customer|the deal|is interested|plans to buy|needs? (?:a|our|the)|approved budget"
                             r"|has a budget)\b", q, re.I)
        assert not re.search(r"Nivarque|tier|price", q)


def test_the_coverage_requires_all_five_areas_in_the_recommendations():
    t = [topics(bundle(OUTREACH))["discovery:qualification"]]
    full = rec("Ask which systems and workflows Halden uses today, who would decide and how approval works, whether "
               "budget or funding is available or still to be authorized, on what timing, and which security, "
               "hosting or integration requirements apply.")
    draft = {"sections": {"meeting_recommendations": [full]}, "disclosures": []}
    assert contract.coverage(draft, t)["topics"]["discovery:qualification"] == "communicated"
    narrow = {"sections": {"meeting_recommendations": [rec("Ask which systems Halden uses today and who decides, "
                                                            "and when.")]}, "disclosures": []}
    cov = contract.coverage(narrow, t)
    assert cov["topics"]["discovery:qualification"] == "cited_only"
    assert cov["missing_capabilities"]["discovery:qualification"] == [
        "budget or funding status", "scope, security, deployment or integration constraints"]


# --- no introductory questions where they are irrelevant ------------------------------------------------------------

@pytest.mark.parametrize("b", [
    bundle(INQUIRY, meetings=[MEETING]),                     # an approved meeting record
    bundle(INQUIRY + [PROPOSAL]),                            # an approved proposal
    bundle(INQUIRY, purpose="negotiation"),                  # other purposes: as agreed, introductions and general
    bundle(INQUIRY, purpose="follow_up"),
    bundle(INQUIRY, purpose="product_demo"),
])
def test_no_qualification_questions_for_established_leads_or_other_purposes(b):
    assert not [t for t in topics(b) if t.startswith("discovery:")]


def test_a_new_lead_keeps_the_existing_questions_without_a_budget_question():
    t = topics(bundle(gaps=NEW))
    assert "discovery:qualification" not in t
    assert t["discovery:buying_context"]["labels"] == ["current systems", "who decides and how", "timing"]
    assert "whether budget" not in t["discovery:buying_context"]["requirement"]
    assert "do not imply a relationship, a need, a budget or an intention to buy" in \
        t["discovery:buying_context"]["requirement"]


# --- the disclosure of what the records do not establish -------------------------------------------------------------

def test_an_early_stage_lead_discloses_only_what_its_correspondence_does_not_establish():
    [u] = cc.unknowns(bundle(INQUIRY))
    for part in ("which systems and workflows Halden Build Group uses today",
                 "who at Halden Build Group would evaluate and decide on tools of this kind",
                 "whether budget or funding is available or authorized (none is assumed)"):
        assert part in u["text"], part
    assert "timing" not in u["text"] and "hosting" not in u["text"]  # the inquiry addresses both
    [u] = cc.unknowns(bundle(OUTREACH))
    assert "the timing of any decision" in u["text"] and "security, hosting or deployment" in u["text"]
    assert "unknown:business" in {d["id"] for d in required_disclosures(bundle(OUTREACH))}


def test_an_established_lead_gets_no_qualification_unknowns():
    for b in (bundle(INQUIRY, meetings=[MEETING]), bundle(INQUIRY + [PROPOSAL])):
        assert not [u for u in cc.unknowns(b) if "budget" in u["text"] or "uses today" in u["text"]]
