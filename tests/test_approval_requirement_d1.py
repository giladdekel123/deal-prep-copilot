"""D1 (owner-approved 2026-11-18): when an approved customer record asks for commercial terms and the policy with the
discount-approval thresholds is in the drafting input, the contract requires the approval authority and conditions to
be stated, for any meeting purpose. Boundary (the vendor policy): up to 15% an account executive; above 15% through
25% the regional sales director's written approval; above 25% the CFO. Approval is never stated as granted. No request
(or a request only in a draft note) means no approval language. Invented customer; the real policy wording."""
import re

import pytest

from deal_prep import contract, selection

POLICY = ("Discount approval policy Account executives may approve discounts of up to 15 percent from the list price. "
          "Discounts above 15 percent require written approval from the regional sales director. Discounts above 25 "
          "percent require approval from the CFO.")


def passage(eid, text, doc_type, **meta):
    doc = eid.split("#")[0]
    m = {"document_id": doc, "doc_type": doc_type, "approval_status": "approved", "info_origin": "synthetic_record",
         "conflict_group": "", **meta}
    return {"evidence_id": eid, "document_id": doc, "info_origin": "synthetic_record", "text": text, "metadata": m,
            "provenance_label": f"SYNTHETIC RECORD · {doc}"}


def bundle(request, purpose="follow_up", status="approved", policy_reason="purpose_document:commercial_request:"
                                                                       "COR-5#2:policy"):
    pol = passage("POL-1#0", POLICY, "policy", scope="global")
    cor = [passage("COR-5#1", "Please send a revised quote for 200 users.", "correspondence", customer_org_id="halden",
                   scope="company"),
           passage("COR-5#2", request, "correspondence", customer_org_id="halden", scope="company",
                   approval_status=status)]
    selected = {"POL-1#0": policy_reason}
    return {"purpose": purpose, "created_at": "2026-11-15T10:00:00+00:00", "identity": {"name": "Halden Build Group",
            "org_id": "halden"}, "selection": {"selected": selected, "products_in_play": []},
            "internal": {"relationship_history": {"sections": [], "evidence": cor},
                         "vendor_products_pricing": {"sections": [], "evidence": [pol]},
                         "meeting_history": {"sections": [], "evidence": []}}, "external": None, "gaps": []}


def approval(b):
    return {t["id"]: t for t in contract.essential_topics(b)}.get("approval_requirement")


@pytest.mark.parametrize("percent, approver, marker_text", [
    (15, "the authority of account executives", "An account executive can approve this."),
    (20, "written approval from the regional sales director", "It needs the regional sales director's approval."),
    (25, "written approval from the regional sales director", "It needs written approval from the regional sales "
                                                              "director."),       # exactly 25%: not the CFO
    (26, "approval from the CFO", "It needs approval from the CFO."),
    (40, "approval from the CFO", "The CFO must approve."),
])
def test_the_required_approval_follows_the_policy_boundaries(percent, approver, marker_text):
    t = approval(bundle(f"Is a {percent}% discount from the list price possible?"))
    assert f"The request is for {percent}%, which under the policy needs {approver}" in t["requirement"]
    # the thresholds themselves come from the policy text
    for part in ("up to 15% the authority of account executives",
                 "above 15% through 25% written approval from the regional sales director",
                 "above 25% approval from the CFO"):
        assert part in t["requirement"], part
    # coverage: the briefing states the right authority; a wrong one does not satisfy the topic
    ok = {"sections": {"meeting_recommendations": [{"kind": "recommendation", "text": marker_text,
                                                    "evidence_ids": ["POL-1#0"], "claim_type": None}]}}
    assert contract.coverage(ok, [t])["topics"]["approval_requirement"] == "communicated"
    wrong = {"sections": {"meeting_recommendations": [{"kind": "recommendation", "text": "Nobody needs to approve.",
                                                       "evidence_ids": ["POL-1#0"], "claim_type": None}]}}
    assert contract.coverage(wrong, [t])["topics"]["approval_requirement"] == "cited_only"


def test_a_pair_of_markers_distinguishes_the_director_from_the_cfo():
    t25 = approval(bundle("Is a 25% discount possible?"))
    cfo = {"sections": {"meeting_recommendations": [{"kind": "recommendation", "text": "The CFO must approve.",
                                                     "evidence_ids": ["POL-1#0"], "claim_type": None}]}}
    assert contract.coverage(cfo, [t25])["topics"]["approval_requirement"] == "cited_only"


@pytest.mark.parametrize("purpose", ["follow_up", "general", "introduction", "product_demo"])
def test_it_applies_across_meeting_purposes(purpose):
    assert approval(bundle("Is a 20% discount possible?", purpose=purpose))


def test_a_negotiation_gains_the_request_in_its_existing_approval_topic_not_a_second_topic():
    b = bundle("We are asking for a 25% discount from the list price.", purpose="negotiation",
               policy_reason="purpose_document:negotiation:policy")
    topics = {t["id"]: t for t in contract.essential_topics(b)}
    assert "approval_requirement" not in topics
    req = topics["approval_policy"]["requirement"]
    assert "asks for commercial terms" in req and "needs written approval from the regional sales director" in req


def test_a_request_without_a_percentage_states_the_thresholds_only():
    t = approval(bundle("Could you offer a better price for the second site?"))
    assert "above 25% approval from the CFO" in t["requirement"] and "The request is for" not in t["requirement"]


@pytest.mark.parametrize("b", [
    bundle("Please send pricing for 250 users."),                                          # no discount request
    bundle("Here is the outline at list prices, with no discount."),                       # a statement
    bundle("Is a 20% discount possible?", status="draft"),                                 # a draft note never counts
    bundle("Is a 20% discount possible?", policy_reason="ranked_search:vendor_products_pricing"),  # policy not for it
])
def test_no_request_no_approval_language(b):
    assert approval(b) is None
    assert all("approval" not in t["requirement"].casefold() for t in contract.essential_topics(b)
               if t["id"] not in ("customer_request:COR-5",) and not t["id"].startswith("customer_request"))


def test_the_requirement_never_says_approval_was_granted():
    t = approval(bundle("Is a 20% discount possible?"))
    assert "do not state or imply that any approval has been granted or that the discount will be offered" \
        in t["requirement"]
    positive = t["requirement"].replace("do not state or imply that any approval has been granted", "")
    assert not re.search(r"\b(?:is|was|has been) (?:approved|granted)\b", positive, re.I)


def test_the_request_reader_names_the_discount_not_another_percentage():
    assert selection.requested_percent("Is a 20% discount on 300 licences, billed 50% upfront, possible?") == 20.0
    assert selection.requested_percent("Is a discount possible?") is None
    assert selection.requested_percent("We want 10% or 15% off.") is None
