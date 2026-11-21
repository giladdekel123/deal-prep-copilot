"""The whole v1 corpus: provenance, coverage of formats and fixtures, and labelling (AT-25)."""
import pytest

from deal_prep.kb_index import load_kb_chunks, load_manifest
from deal_prep.provenance import KB_DIR, load_registry

MANIFEST = load_manifest()
SYNTHETIC = [d for d in MANIFEST if d["info_origin"] == "synthetic_record"]
REGISTRY = load_registry()


@pytest.fixture(scope="module")
def chunks():
    return load_kb_chunks()


def test_whole_corpus_passes_validator_and_chunks(chunks):
    assert {c["metadata"]["document_id"] for c in chunks} == {d["document_id"] for d in MANIFEST}


def test_synthetic_manifest_and_files_match_one_to_one():
    listed = {d["file_path"] for d in SYNTHETIC}
    on_disk = {f"synthetic/{p.name}" for p in (KB_DIR / "synthetic").iterdir()}
    assert listed == on_disk


def test_first_tranche_size_and_all_five_formats():
    assert 17 <= len(MANIFEST) <= 20
    assert {d["file_type"] for d in SYNTHETIC} == {"md", "txt", "docx", "xlsx", "pdf"}


def test_conflict_fixtures_c1_to_c4_present():
    groups = {}
    for d in MANIFEST:
        if d.get("conflict_group"):
            groups.setdefault(d["conflict_group"], []).append(d["document_id"])
    assert sorted(groups["C1"]) == ["NVQ-PRC-2025-v1", "NVQ-PRC-2026-v1"]
    assert sorted(groups["C2"]) == ["NVQ-POL-002", "NVQ-PRD-001"]
    assert groups["C3"] == ["NVQ-PRP-002"]
    assert groups["C4"] == ["NVQ-MTG-002"]


def test_every_record_about_a_real_company_is_labelled_synthetic(chunks):
    for c in chunks:
        meta = c["metadata"]
        if meta["info_origin"] == "synthetic_record" and meta["involves_real_org"]:
            assert meta["synthetic_relationship"] is True
            assert meta["provenance_label"].startswith("SYNTHETIC — not a real business fact")
            assert "(real, customer)" in meta["provenance_label"]


def test_ashtrom_has_no_synthetic_relationship_records():
    for d in SYNTHETIC:
        assert all(o["org_id"] != "ashtrom_group" for o in d["organizations"]), d["document_id"]


def test_banners_are_not_indexed_as_passages(chunks):
    assert not any(c["text"].lstrip("> ").startswith("SYNTHETIC") for c in chunks)


def test_prompt_injection_text_is_stored_only_as_labelled_synthetic_evidence(chunks):
    hits = [c for c in chunks if "ignore all previous instructions" in c["text"]]
    assert hits and all(c["metadata"]["document_id"] == "NVQ-COR-001" for c in hits)
    assert all(c["metadata"]["info_origin"] == "synthetic_record" for c in hits)


def test_every_chunk_has_complete_provenance(chunks):
    for c in chunks:
        meta = c["metadata"]
        assert meta["info_origin"] and meta["creation_method"] and meta["provenance_label"]
        if meta["info_origin"] == "public_source":
            assert meta["source_url"] in meta["provenance_label"]
            assert meta["retrieved_at"] and meta["publication_date"] and meta["verification_status"]
