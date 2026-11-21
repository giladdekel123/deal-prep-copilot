"""Registry and provenance validator (spec v1.2 §6B, AT-25).

Valid samples must pass; each broken sample violates one rule and must be rejected
with an error naming that rule. Samples are in-memory, so no corpus files are needed yet.
"""
import copy

import pytest

from deal_prep.provenance import (SYNTHETIC_BANNER, ProvenanceError, assert_valid,
                                  load_registry, validate_document, validate_registry)

REGISTRY = load_registry()

VENDOR_TEXT = "Nivarque Engineering Vault provides a drawing register and transmittals."
RELATIONSHIP_TEXT = f"> {SYNTHETIC_BANNER}\n\nProposal to Arup for Nivarque Engineering Vault."
PUBLIC_TEXT = "Arup is an international consultancy with deep technical and advisory expertise."  # fixture text, not from a source page


def vendor_doc():
    return {"document_id": "NVQ-PRD-001", "info_origin": "synthetic_record",
            "creation_method": "authored_fixture",
            "organizations": [{"org_id": "nivarque", "role": "vendor"}]}


def relationship_doc():
    return {"document_id": "NVQ-PRP-001", "info_origin": "synthetic_record",
            "creation_method": "generated_fixture",
            "organizations": [{"org_id": "nivarque", "role": "vendor"},
                              {"org_id": "arup", "role": "customer"}],
            "synthetic_relationship": True, "synthetic_categories": ["proposal", "price"]}


def public_doc():
    return {"document_id": "NVQ-PUB-001", "info_origin": "public_source",
            "creation_method": "curated_snapshot",
            "organizations": [{"org_id": "arup", "role": "subject"}],
            "source_url": "https://www.arup.com/about-us/", "publisher": "Arup",
            "publication_date": "unknown", "retrieved_at": "2026-11-05",
            "verification_status": "primary",
            "excerpts": [{"excerpt_id": "E1", "text": PUBLIC_TEXT}],
            "claims": [{"text": "Arup is a global consultancy.", "excerpt_id": "E1"}]}


# --- registry -----------------------------------------------------------------

def test_registry_file_is_valid():
    assert validate_registry(list(REGISTRY.values())) == []


def test_registry_contains_approved_organizations():
    assert {o: REGISTRY[o]["reality"] for o in REGISTRY} == {
        "nivarque": "fictional", "solquend": "fictional", "shikun_binui": "real",
        "ashtrom_group": "real", "arup": "real", "arup_laboratories": "real"}
    assert REGISTRY["arup_laboratories"].get("public_only") is True


@pytest.mark.parametrize("mutate, expected", [
    (lambda o: o[0].update(reality="maybe"), "reality must be one of"),
    (lambda o: o[2].update(official_domain=None), "needs official_domain"),
    (lambda o: o[2].update(identity_sources=["http://insecure.example"]), "https identity_sources"),
    (lambda o: o[0].update(identity_sources=["https://example.com"]), "must not cite identity sources"),
    (lambda o: o.append(copy.deepcopy(o[0])), "duplicate org_id"),
])
def test_broken_registry_rejected(mutate, expected):
    orgs = copy.deepcopy(list(REGISTRY.values()))
    mutate(orgs)
    assert any(expected in e for e in validate_registry(orgs))


# --- valid documents ------------------------------------------------------------

@pytest.mark.parametrize("doc, text", [
    (vendor_doc(), VENDOR_TEXT),
    (relationship_doc(), RELATIONSHIP_TEXT),
    (public_doc(), PUBLIC_TEXT),
])
def test_valid_samples_pass(doc, text):
    assert validate_document(doc, text, REGISTRY) == []
    assert_valid(doc, text, REGISTRY)


def test_vendor_only_synthetic_needs_no_banner():
    assert validate_document(vendor_doc(), VENDOR_TEXT, REGISTRY) == []


# --- broken documents: each violates exactly one rule ----------------------------

BROKEN = [
    # identity, origin and creation method
    ("prompt01_prefix", vendor_doc, VENDOR_TEXT, lambda d: d.update(document_id="DMS-PRD-001"), "DMS-* is reserved"),
    ("third_origin_value", vendor_doc, VENDOR_TEXT, lambda d: d.update(info_origin="user_entered_demo"), "info_origin must be one of"),
    ("method_wrong_for_origin", public_doc, PUBLIC_TEXT, lambda d: d.update(creation_method="authored_fixture"), "not allowed for public_source"),
    ("pub_id_but_synthetic", vendor_doc, VENDOR_TEXT, lambda d: d.update(document_id="NVQ-PUB-009"), "PUB documents must be public_source"),
    ("unknown_org", vendor_doc, VENDOR_TEXT, lambda d: d["organizations"].append({"org_id": "acme", "role": "customer"}), "unknown org_id"),
    ("invalid_role", vendor_doc, VENDOR_TEXT, lambda d: d["organizations"][0].update(role="owner"), "invalid role"),
    ("no_organizations", vendor_doc, VENDOR_TEXT, lambda d: d.update(organizations=[]), "at least one"),
    # rule 1: public sources and fictional organizations
    ("public_refs_fictional_org", public_doc, PUBLIC_TEXT, lambda d: d["organizations"].append({"org_id": "nivarque", "role": "vendor"}), "references fictional organization"),
    # rule 2: synthetic records about real organizations
    ("missing_banner", relationship_doc, "Proposal to Arup.", lambda d: None, "missing the mandatory banner"),
    ("missing_relationship_flag", relationship_doc, RELATIONSHIP_TEXT, lambda d: d.pop("synthetic_relationship"), "synthetic_relationship: true"),
    ("empty_categories", relationship_doc, RELATIONSHIP_TEXT, lambda d: d.update(synthetic_categories=[]), "synthetic_categories"),
    ("invalid_category", relationship_doc, RELATIONSHIP_TEXT, lambda d: d.update(synthetic_categories=["gossip"]), "synthetic_categories"),
    ("synthetic_about_public_only_org", relationship_doc, RELATIONSHIP_TEXT,
     lambda d: d["organizations"].__setitem__(1, {"org_id": "arup_laboratories", "role": "customer"}), "public-only organization"),
    # rule 3: public-source required fields
    ("missing_source_url", public_doc, PUBLIC_TEXT, lambda d: d.pop("source_url"), "source_url must be an https URL"),
    ("http_source_url", public_doc, PUBLIC_TEXT, lambda d: d.update(source_url="http://www.arup.com/"), "source_url must be an https URL"),
    ("missing_publisher", public_doc, PUBLIC_TEXT, lambda d: d.update(publisher=""), "publisher is required"),
    ("missing_publication_date", public_doc, PUBLIC_TEXT, lambda d: d.pop("publication_date"), "publication_date must be"),
    ("invalid_publication_date", public_doc, PUBLIC_TEXT, lambda d: d.update(publication_date="recently"), "publication_date must be"),
    ("missing_retrieved_at", public_doc, PUBLIC_TEXT, lambda d: d.pop("retrieved_at"), "retrieved_at must be"),
    ("invalid_verification", public_doc, PUBLIC_TEXT, lambda d: d.update(verification_status="trusted"), "verification_status must be"),
    ("no_excerpts", public_doc, PUBLIC_TEXT, lambda d: d.update(excerpts=[]), "supporting excerpt is required"),
    ("excerpt_too_long", public_doc, PUBLIC_TEXT, lambda d: d["excerpts"][0].update(text="word " * 51), "exceeds 50 words"),
    ("claim_unlinked", public_doc, PUBLIC_TEXT, lambda d: d["claims"][0].update(excerpt_id="E9"), "not linked to a stored excerpt"),
    ("no_claims", public_doc, PUBLIC_TEXT, lambda d: d.update(claims=[]), "at least one claim"),
]


@pytest.mark.parametrize("name, factory, text, mutate, expected", BROKEN, ids=[b[0] for b in BROKEN])
def test_broken_sample_rejected(name, factory, text, mutate, expected):
    doc = factory()
    mutate(doc)
    errors = validate_document(doc, text, REGISTRY)
    assert any(expected in e for e in errors), errors
    with pytest.raises(ProvenanceError):
        assert_valid(doc, text, REGISTRY)


def test_public_text_mentioning_fictional_org_rejected():
    errors = validate_document(public_doc(), PUBLIC_TEXT + " Arup evaluated Nivarque.", REGISTRY)
    assert any("mentions fictional organization 'Nivarque" in e for e in errors), errors


def test_publication_date_unknown_is_allowed_but_not_missing():
    doc = public_doc()
    assert doc["publication_date"] == "unknown"
    assert validate_document(doc, PUBLIC_TEXT, REGISTRY) == []
