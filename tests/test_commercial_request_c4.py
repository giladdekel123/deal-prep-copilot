"""C4.1 (owner-approved 2026-11-17): the commercial policy is chosen by the request. Besides a negotiation and a
current proposal (unchanged), the policy comes with any purpose when the customer's approved records ask for
commercial terms in request form. A statement, a figure of speech ("discounted cash flow"), a request for plain
pricing, or a request found only in a draft note brings nothing. Invented companies; the knowledge base is faked."""
from datetime import date

import pytest

from deal_prep import selection

TODAY = date(2026, 11, 15)


@pytest.mark.parametrize("sentence", [
    "Is a 20% discount from the list price possible?",
    "For a 36-month commitment we are asking for a 25% discount from the list price.",
    "The customer asked for a better 36-month price.",
    "We would like to discuss extended payment terms.",
    "Could you offer special pricing for the second site?",
    "They requested a rebate on the unused licences.",
    "Is any price reduction possible for 300 users?",
])
def test_requests_for_commercial_terms_are_recognized(sentence):
    assert selection.commercial_request([{"evidence_id": "R#1", "text": sentence}]) == "R#1"


@pytest.mark.parametrize("sentence", [
    "Here is an indicative outline at the 2026 list prices, with no discount.",   # a statement
    "Please send pricing for 250 users.",                                          # plain pricing, no terms
    "The valuation uses a discounted cash flow model. Can you share it?",          # not a commercial term
    "The 10 percent discount is within account executive authority.",             # a statement of terms
    "Can documents be hosted in Australia?",                                       # a question on another subject
])
def test_statements_and_other_questions_are_not_requests(sentence):
    assert selection.commercial_request([{"evidence_id": "R#1", "text": sentence}]) is None


REQUEST = {"evidence_id": "COR-5#2", "metadata": {"doc_type": "correspondence"},
           "text": "Please send a revised quote for 200 users. Is a 20% discount from the list price possible?"}
PLAIN = {"evidence_id": "COR-5#1", "metadata": {"doc_type": "correspondence"}, "text": "Please send pricing."}


@pytest.mark.parametrize("purpose", ["follow_up", "general", "introduction", "product_demo"])
def test_a_request_brings_the_policy_with_its_reason_for_any_purpose(purpose):
    assert selection.context_documents(purpose, [PLAIN, REQUEST], []) == \
        [("commercial_request:COR-5#2", selection.COMMERCIAL_CONTEXT)]


def test_a_request_in_an_approved_meeting_record_counts_and_the_existing_rules_are_unchanged():
    meeting = {"evidence_id": "HIST-MTG-1#0", "text": "The customer asked for a better 36-month price."}
    assert selection.context_documents("follow_up", [PLAIN], [meeting]) == \
        [("commercial_request:HIST-MTG-1#0", selection.COMMERCIAL_CONTEXT)]
    assert selection.context_documents("negotiation", [REQUEST], []) == []  # negotiation already brings it
    proposal = [{"evidence_id": "PRP-1#1", "metadata": {"doc_type": "proposal"}, "text": "Proposal."}]
    assert selection.context_documents("follow_up", proposal + [REQUEST], []) == \
        [("commercial_context", selection.COMMERCIAL_CONTEXT)]  # one policy, for the proposal (as before)
    assert selection.context_documents("follow_up", [PLAIN], []) == []


# --- through the selection step, with a faked knowledge base -------------------------------------------------------

def passage(eid, text, **meta):
    doc = eid.split("#")[0]
    m = {"document_id": doc, "approval_status": "approved", "info_origin": "synthetic_record", **meta}
    return {"evidence_id": eid, "document_id": doc, "text": text, "info_origin": "synthetic_record", "metadata": m,
            "provenance_label": f"SYNTHETIC RECORD · {doc}"}


POLICY = [passage("POL-1#0", "Commercial policy. Discounts above 10 percent need regional sales director approval.",
                  doc_type="policy", scope="global"),
          passage("POL-1#1", "Proposals are valid for 30 days.", doc_type="policy", scope="global")]
PRICES = [passage("PRC-1#1", "List prices Product: Core | Tier: Business | Unit: per user per month | List price "
                             "(USD): 34", doc_type="price_list", scope="global")]


def run(records, monkeypatch, purpose="follow_up", meetings=()):
    kb = POLICY + PRICES + records

    def match(meta, where):
        if "$and" in where:
            return all(match(meta, w) for w in where["$and"])
        return all(meta.get(k) == v for k, v in where.items())
    monkeypatch.setattr(selection, "passages_where", lambda where, chroma_dir=None: [p for p in kb
                                                                                    if match(p["metadata"], where)])
    monkeypatch.setattr(selection, "search", lambda text, k=5, global_only=False, origin=None, chroma_dir=None,
                        **kw: [p for p in kb if p["metadata"].get("scope") == "global"][:k])
    bundle = {"purpose": purpose, "identity": {"name": "Halden Build Group", "org_id": "halden"},
              "internal": {"relationship_history": {"sections": [], "evidence": []},
                           "meeting_history": {"sections": [], "evidence": list(meetings)},
                           "vendor_products_pricing": {"sections": [], "evidence": []}},
              "trace": []}
    selection.select_for_purpose(bundle, None, TODAY)
    return bundle["selection"]["selected"]


def customer(eid, text, status="approved", doc_type="correspondence"):
    return passage(eid, text, doc_type=doc_type, customer_org_id="halden", scope="company", approval_status=status)


def test_the_selection_adds_the_policy_for_an_approved_request_and_records_why(monkeypatch):
    why = run([customer("COR-5#1", "Please send pricing."),
               customer("COR-5#2", "Is a 20% discount from the list price possible?")], monkeypatch)
    assert why["POL-1#0"] == "purpose_document:commercial_request:COR-5#2:policy" and "POL-1#1" in why


def test_a_request_only_in_a_draft_note_or_plain_pricing_brings_no_policy(monkeypatch):
    why = run([customer("COR-5#1", "Please send pricing."),
               customer("MTG-9#1", "Draft notes: they asked whether a 20% discount is possible.", status="draft",
                        doc_type="meeting_notes")], monkeypatch)
    assert "POL-1#0" not in why and "MTG-9#1" not in why
