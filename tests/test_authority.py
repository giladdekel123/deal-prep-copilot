"""Deterministic authority and origin rules on real corpus chunks; no embeddings (C1–C4)."""
from datetime import date

import pytest

from deal_prep import authority
from deal_prep.kb_index import load_kb_chunks, to_evidence
from deal_prep.provenance import load_registry


@pytest.fixture(scope="module")
def ev():
    registry = load_registry()
    return [to_evidence(c["chunk_id"], c["text"], c["metadata"], registry) for c in load_kb_chunks()]


def by_doc(ev, *doc_ids):
    return [e for e in ev if e["document_id"] in doc_ids]


def test_c1_current_price_uses_list_in_force_now(ev):
    r = authority.current_list_price(ev, "Nivarque Core", "Business", date(2026, 11, 6))
    assert r["status"] == "resolved" and r["value"] == "34"
    assert any("NVQ-PRC-2025-v1" in eid and "not in force" in why for eid, why in r["rejected"])


def test_c1_superseded_list_was_in_force_before_its_end_date(ev):
    r = authority.current_list_price(ev, "Nivarque Core", "Business", date(2026, 6, 1))
    assert r["status"] == "resolved" and r["value"] == "30"


def test_c2_conflicting_approved_statements_stay_unresolved(ev):
    scim = [e for e in by_doc(ev, "NVQ-PRD-001", "NVQ-POL-002") if "SCIM" in e["text"]]
    assert {e["document_id"] for e in scim} == {"NVQ-PRD-001", "NVQ-POL-002"}
    r = authority.policy_statement(scim, date(2026, 11, 6))
    assert r["status"] == "unresolved" and len(r["selected"]) == 2


def test_c3_proposal_price_is_never_the_list_price(ev):
    r = authority.current_list_price(ev, "Nivarque Engineering Vault", "Enterprise", date(2026, 11, 6))
    assert r["status"] == "resolved" and r["value"] == "52"
    assert any("NVQ-PRP-002" in eid and "negotiated historical offer" in why for eid, why in r["rejected"])
    offer = authority.historical_offer(ev, "arup", "Nivarque Engineering Vault")
    assert offer["status"] == "resolved"
    assert offer["value"] == {"proposed_price_usd": ["46"], "label": "historical synthetic proposal"}


def test_c4_synthetic_note_cannot_prove_a_real_world_fact(ev):
    claim = [e for e in ev if e["document_id"] == "NVQ-MTG-002" and "1985" in e["text"]]
    public = [e for e in by_doc(ev, "NVQ-PUB-005", "NVQ-PUB-007") if "trust" in e["text"].lower()]
    r = authority.real_world_fact(claim + public)
    assert r["status"] == "unresolved"  # the two public sources disagree (1977 vs 1979)
    assert [eid.split("#")[0] for eid in r["origin_violations"]] == ["NVQ-MTG-002"]
    assert all(eid.split("#")[0] in {"NVQ-PUB-005", "NVQ-PUB-007"} for eid in r["selected"])


def test_c4_synthetic_only_evidence_is_an_origin_violation(ev):
    claim = [e for e in ev if e["document_id"] == "NVQ-MTG-002" and "1985" in e["text"]]
    assert authority.real_world_fact(claim)["status"] == "origin_violation"


def test_public_source_cannot_prove_vendor_price(ev):
    r = authority.current_list_price(by_doc(ev, "NVQ-PUB-003"), "Nivarque Core", "Business", date(2026, 11, 6))
    assert r["status"] == "origin_violation"


def test_draft_meeting_notes_never_count_as_history(ev):
    r = authority.meeting_history(by_doc(ev, "NVQ-MTG-001", "NVQ-MTG-002"))
    assert r["status"] == "resolved"
    assert {eid.split("#")[0] for eid in r["selected"]} == {"NVQ-MTG-001"}
    assert {eid.split("#")[0] for eid, _ in r["rejected"]} == {"NVQ-MTG-002"}


def test_no_valid_source_when_product_unknown(ev):
    r = authority.current_list_price(ev, "Nivarque Quantum", "Ultra", date(2026, 11, 6))
    assert r["status"] == "no_valid_source"
