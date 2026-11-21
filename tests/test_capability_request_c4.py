"""C4.2 (owner-approved 2026-11-17): vendor capability statements chosen by the customer's own questions. For each
capability question or requirement in the customer's approved records (at most four), one ranked search within the
vendor's product-overview and policy documents in force; the best passage of each document is kept within the
distance threshold and when it shares a content term with the question. Draft notes never ask; commercial-only and
plain requests ask nothing; other document types are never searched. The existing conflict-source step adds the other
side of a conflict a kept passage states. Invented companies (the knowledge base is faked), plus the kb_v1 index."""
from datetime import date, datetime, timezone

import pytest

from deal_prep import selection

TODAY = date(2026, 11, 15)
NAMES = frozenset({"nivarque", "core", "business", "engineering", "vault", "enterprise"})


@pytest.mark.parametrize("sentence, terms", [
    ("Is SCIM provisioning included in Core Business?", {"scim", "provision"}),
    ("We also need SCIM user provisioning for all 1,050 users, including the 300 Core Business users.",
     {"scim", "provision"}),
    ("Can documents be hosted in Australia?", {"host", "australia"}),
    ("The SCIM question is still open.", {"scim"}),
    ("Does the private-cloud option also cover the Core users?", {"private-cloud", "private", "cloud"}),
    ("The contact asked whether transmittals can be exported to their contractors in PDF form.",
     {"contact", "transmittal", "export", "contractor", "pdf", "form"}),
])
def test_capability_questions_and_requirements_are_recognized(sentence, terms):
    [(eid, found, got)] = selection.capability_questions([{"evidence_id": "R#1", "text": sentence}], NAMES)
    assert eid == "R#1" and found == sentence and got == terms


@pytest.mark.parametrize("sentence", [
    "Please send a revised quote for 200 users.",                                     # a request, not a question
    "Is a 20% discount from the list price possible?",                                # commercial only (C4.1)
    "For a 36-month commitment we are asking for a 25% discount from the Engineering Vault list price.",
    "We confirmed that transmittal export to PDF is included in Engineering Vault.",  # a statement
    "Status: no proposal sent; no other contact recorded.",
])
def test_statements_and_commercial_requests_are_not_capability_questions(sentence):
    assert selection.capability_questions([{"evidence_id": "R#1", "text": sentence}], NAMES) == []


def test_at_most_four_questions_are_searched():
    text = " ".join(f"Do you support feature{n} for us?" for n in "ABCDEF")
    assert len(selection.capability_questions([{"evidence_id": "R#1", "text": text}], NAMES)) == 4


# --- the search: best passage per vendor document, threshold, shared term, document type, in force ---------------

def vendor(eid, text, doc_type, distance, **meta):
    doc = eid.split("#")[0]
    m = {"document_id": doc, "doc_type": doc_type, "approval_status": "approved", "scope": "global",
         "info_origin": "synthetic_record", **meta}
    return {"evidence_id": eid, "document_id": doc, "text": text, "info_origin": "synthetic_record", "metadata": m,
            "distance": distance, "provenance_label": f"SYNTHETIC RECORD · {doc}"}


RANKED = [
    vendor("BAT-1#1", "Competitor X offers SCIM provisioning on every tier.", "battlecard", 0.40),
    vendor("PRD-1#3", "SCIM user provisioning is available on the Enterprise tier only.", "product_overview", 0.63),
    vendor("PRD-1#0", "Product family Nivarque Core is a document management system.", "product_overview", 0.64),
    vendor("OLD-1#2", "SCIM provisioning is included in every tier.", "policy", 0.66, approval_status="superseded"),
    vendor("PRC-1#1", "List prices Product: Core | Tier: Business | List price (USD): 34", "price_list", 0.70),
    vendor("POL-2#2", "SCIM user provisioning is available on the Business and Enterprise tiers.", "policy", 0.75),
    vendor("POL-1#0", "Discount approval policy: discounts above 15 percent need approval.", "policy", 0.79),
    vendor("FAR-1#1", "SCIM provisioning roadmap notes.", "product_overview", 0.86),
]


def fake_search(monkeypatch, ranked=RANKED):
    calls = []

    def search(text, k=5, global_only=False, origin=None, chroma_dir=None, **kw):
        calls.append((text, global_only, origin))
        return ranked[:k]
    monkeypatch.setattr(selection, "search", search)
    return calls


def test_the_best_passage_of_each_vendor_document_within_the_threshold_sharing_a_term_is_kept(monkeypatch):
    calls = fake_search(monkeypatch)
    got = selection.capability_passages([{"evidence_id": "COR-5#2", "text": "Is SCIM provisioning included in "
                                                                            "Core Business?"}], TODAY, None, NAMES)
    assert [(a, p["evidence_id"]) for a, p in got] == [("COR-5#2", "PRD-1#3"), ("COR-5#2", "POL-2#2")]
    # not kept: a battlecard and a price list (not searched document types), a superseded policy, the second passage
    # of a document, a policy passage sharing no term with the question, a passage beyond the threshold
    assert calls == [("Is SCIM provisioning included in Core Business?", True, "synthetic_record")]


def test_no_question_means_no_search(monkeypatch):
    calls = fake_search(monkeypatch)
    assert selection.capability_passages([{"evidence_id": "COR-5#1", "text": "Please send pricing."}], TODAY, None,
                                         NAMES) == []
    assert calls == []


# --- through the selection step, with a faked knowledge base -------------------------------------------------------

def record(eid, text, status="approved", doc_type="correspondence"):
    doc = eid.split("#")[0]
    m = {"document_id": doc, "doc_type": doc_type, "approval_status": status, "customer_org_id": "halden",
         "scope": "company", "info_origin": "synthetic_record"}
    return {"evidence_id": eid, "document_id": doc, "text": text, "info_origin": "synthetic_record", "metadata": m,
            "provenance_label": f"SYNTHETIC RECORD · {doc}"}


def select(records, monkeypatch, purpose="follow_up"):
    kb = [p for p in RANKED if p["metadata"]["doc_type"] != "battlecard"] + records

    def match(meta, where):
        if "$and" in where:
            return all(match(meta, w) for w in where["$and"])
        return all(meta.get(k) == v for k, v in where.items())
    monkeypatch.setattr(selection, "passages_where", lambda where, chroma_dir=None: [p for p in kb
                                                                                    if match(p["metadata"], where)])
    fake_search(monkeypatch)
    bundle = {"purpose": purpose, "identity": {"name": "Halden Build Group", "org_id": "halden"},
              "internal": {"relationship_history": {"sections": [], "evidence": []},
                           "meeting_history": {"sections": [], "evidence": []},
                           "vendor_products_pricing": {"sections": [], "evidence": []}},
              "trace": []}
    selection.select_for_purpose(bundle, None, TODAY)
    return bundle["selection"]["selected"], [e["evidence_id"] for e in bundle["internal"]["vendor_products_pricing"]
                                             ["evidence"]]


def test_an_approved_question_brings_the_capability_statements_with_its_reason(monkeypatch):
    why, vendor_ids = select([record("COR-5#2", "Is SCIM provisioning included in Core Business?")], monkeypatch)
    assert why["PRD-1#3"] == why["POL-2#2"] == "capability_request:COR-5#2"
    assert {"PRD-1#3", "POL-2#2"} <= set(vendor_ids)


def test_a_question_only_in_a_draft_note_brings_nothing(monkeypatch):
    why, _ = select([record("COR-5#1", "Please send pricing."),
                     record("MTG-9#1", "Draft notes: is SCIM provisioning included?", status="draft",
                            doc_type="meeting_notes")], monkeypatch)
    assert not [r for r in why.values() if r.startswith("capability_request:")]


# --- the kb_v1 index: a real approved question, a draft-only question, and the other side of a conflict -----------

@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    from deal_prep.kb_index import build_kb_index
    d = tmp_path_factory.mktemp("capability_kb")
    build_kb_index(chroma_dir=d)
    return d


def kb_bundle(org, name, purpose="follow_up"):
    """The selection step adds every passage of the customer's approved records itself."""
    return {"purpose": purpose, "identity": {"name": name, "org_id": org},
            "internal": {"relationship_history": {"sections": [], "evidence": []},
                         "meeting_history": {"sections": [], "evidence": []},
                         "vendor_products_pricing": {"sections": [], "evidence": []}},
            "trace": [], "created_at": "2026-11-15T10:00:00+00:00"}


def test_an_approved_capability_question_finds_the_vendor_statement_and_keeps_an_earlier_reason(kb):
    """The approved correspondence asks whether transmittals can be exported; the statement that answers it is the
    Engineering Vault description, which the selection already includes as a product in play: it is found, it is in
    the drafting input once, and it keeps its earlier reason (C4.2 adds only what is new)."""
    b = kb_bundle("shikun_binui", "Shikun & Binui")
    selection.select_for_purpose(b, kb, TODAY)
    records = selection.customer_records("shikun_binui", kb)
    [(asked, sentence, _)] = selection.capability_questions(records, NAMES)
    assert asked.startswith("NVQ-COR-001#") and "transmittals" in sentence
    found = [p["evidence_id"] for _, p in selection.capability_passages(records, TODAY, kb, NAMES)]
    vendor_ids = [e["evidence_id"] for e in b["internal"]["vendor_products_pricing"]["evidence"]]
    assert found and all(vendor_ids.count(i) == 1 for i in found)
    assert all(b["selection"]["selected"][i].startswith("product_in_play:") for i in found)


def test_a_question_only_in_a_draft_meeting_note_of_the_knowledge_base_brings_nothing(kb):
    b = kb_bundle("arup", "Arup")  # the encryption-key question is only in Arup's draft meeting notes
    selection.select_for_purpose(b, kb, TODAY)
    assert not [eid for eid, r in b["selection"]["selected"].items() if r.startswith("capability_request:")
                and "MTG-002" in r]
    assert not [eid for eid, r in b["selection"]["selected"].items() if r.startswith("capability_request:")
                and "encrypt" in next(e["text"] for e in b["internal"]["vendor_products_pricing"]["evidence"]
                                      if e["evidence_id"] == eid).casefold()]


def test_the_conflict_source_step_adds_the_other_side_of_a_capability_statement(kb):
    from deal_prep import orchestrator
    from deal_prep.kb_index import document_passages
    one_side = next(p for p in document_passages("NVQ-PRD-001", kb) if "Enterprise tier only" in p["text"])
    b = {"internal": {"vendor_products_pricing": {"sections": [], "evidence": [one_side]}}, "trace": []}
    orchestrator.add_conflict_sources(b, kb, datetime(2026, 11, 15, tzinfo=timezone.utc))
    added = b.get("conflict_sources") or []
    assert any(p["document_id"] == "NVQ-POL-002" and "Business and Enterprise tiers" in p["text"] for p in added)
