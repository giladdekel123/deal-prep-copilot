"""Public-source snapshots in data/kb_v1 (Gate 2B step 4; spec v1.2 §6B, AT-24, AT-25)."""
import json

import pytest

from deal_prep.corpus import extract_text, resolve_document_path
from deal_prep.provenance import KB_DIR, load_registry, validate_document

MANIFEST = json.loads((KB_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
PUBLIC = [d for d in MANIFEST if d["info_origin"] == "public_source"]
REGISTRY = load_registry()
NEXASTREAM_TOKENS = ["NexaStream", "CloudNova", "QuantaLake", "InsightForge", "DataSphere"]


def _text(doc):
    return extract_text(resolve_document_path(doc, corpus_dir=KB_DIR))


@pytest.mark.parametrize("doc", PUBLIC, ids=[d["document_id"] for d in PUBLIC])
def test_public_document_passes_provenance_validator(doc):
    assert validate_document(doc, _text(doc), REGISTRY) == []


def test_public_manifest_and_files_match_one_to_one():
    listed = {d["file_path"] for d in PUBLIC}
    on_disk = {f"public/{p.name}" for p in (KB_DIR / "public").iterdir()}
    assert listed == on_disk


def test_document_ids_unique():
    ids = [d["document_id"] for d in MANIFEST]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("doc", PUBLIC, ids=[d["document_id"] for d in PUBLIC])
def test_excerpts_and_claims_appear_verbatim_in_file(doc):
    text = _text(doc)
    for ex in doc["excerpts"]:
        assert f'[{ex["excerpt_id"]}] "{ex["text"]}"' in text, ex["excerpt_id"]
    for claim in doc["claims"]:
        assert f'[{claim["claim_id"]}] {claim["text"]} ({claim["excerpt_id"]})' in text, claim["claim_id"]


@pytest.mark.parametrize("doc", PUBLIC, ids=[d["document_id"] for d in PUBLIC])
def test_file_header_matches_manifest_provenance(doc):
    text = _text(doc)
    assert text.startswith("# PUBLIC SOURCE")
    assert doc["source_url"] in text
    assert f'**Retrieved:** {doc["retrieved_at"]}' in text
    assert f'**Publication date:** {doc["publication_date"]}' in text
    assert f'**Verification:** {doc["verification_status"]}' in text


def test_every_real_organization_has_a_public_profile():
    covered = {o["org_id"] for d in PUBLIC for o in d["organizations"]}
    real = {oid for oid, o in REGISTRY.items() if o["reality"] == "real"}
    assert real <= covered


def test_public_only_organization_appears_only_in_public_sources():
    for d in MANIFEST:
        if any(o["org_id"] == "arup_laboratories" for o in d["organizations"]):
            assert d["info_origin"] == "public_source", d["document_id"]


def test_arup_trust_year_conflict_is_kept_not_resolved():
    group = [d for d in PUBLIC if d.get("conflict_group") == "PUB-ARUP-TRUST-YEAR"]
    assert {d["document_id"] for d in group} == {"NVQ-PUB-005", "NVQ-PUB-007"}
    years = {d["document_id"]: next(c["text"] for c in d["claims"] if "trust" in c["text"].lower()) for d in group}
    assert "1977" in years["NVQ-PUB-005"] and "1979" in years["NVQ-PUB-007"]
    for d in group:
        # Owner reassessment: a possible chronological ambiguity, still unresolved (neither date chosen).
        text = " ".join(_text(d).split())
        assert "Possible chronological ambiguity, not a proven contradiction" in text
        assert "neither date is chosen" in text
        assert d["fixture_tag"] == "real_source_chronological_ambiguity"


def test_arup_1977_claim_does_not_overstate_its_excerpt():
    # The 1977 excerpt dates a decision to pass ownership, not completed trust ownership.
    pub5 = next(d for d in PUBLIC if d["document_id"] == "NVQ-PUB-005")
    claim = next(c for c in pub5["claims"] if c["claim_id"] == "C2")
    excerpt = next(e for e in pub5["excerpts"] if e["excerpt_id"] == claim["excerpt_id"])
    assert "decision" in claim["text"] and "decision" in excerpt["text"]
    assert "ownership passed" not in claim["text"]


@pytest.mark.parametrize("doc", PUBLIC, ids=[d["document_id"] for d in PUBLIC])
def test_no_classroom_content(doc):
    text = _text(doc).lower()
    assert not any(t.lower() in text for t in NEXASTREAM_TOKENS)
