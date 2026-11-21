"""dms_kb_v1 indexing with provenance enforcement, company scoping and name resolution (offline)."""
import copy

import pytest

from deal_prep.index import _client
from deal_prep.kb_index import (KB_COLLECTION, bm25_rank, build_kb_index, check_chunk_metadata,
                                embedding_text, load_kb_chunks, load_manifest, resolve_company, search)
from deal_prep.provenance import ProvenanceError


@pytest.fixture(scope="module")
def kb_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("kb_chroma")
    build_kb_index(chroma_dir=d)
    return d


def test_every_stored_record_has_complete_provenance(kb_dir):
    got = _client(kb_dir).get_collection(KB_COLLECTION, embedding_function=None).get(include=["metadatas"])
    assert got["ids"]
    for meta in got["metadatas"]:
        check_chunk_metadata(meta)


def test_invalid_document_blocks_the_whole_build(tmp_path):
    manifest = copy.deepcopy(load_manifest())
    bad = next(d for d in manifest if d["document_id"] == "NVQ-PUB-004")
    del bad["source_url"]
    with pytest.raises(ProvenanceError, match="source_url"):
        build_kb_index(chroma_dir=tmp_path, manifest=manifest)
    assert KB_COLLECTION not in [c.name for c in _client(tmp_path).list_collections()]


def test_chunk_with_missing_origin_refused():
    with pytest.raises(ProvenanceError, match="info_origin"):
        check_chunk_metadata({"chunk_id": "X#0", "document_id": "X", "creation_method": "authored_fixture",
                              "scope": "global", "organizations_json": "[]", "provenance_label": "x"})


def test_company_scope_excludes_other_companies(kb_dir):
    for company, query in [("arup", "nonprofit laboratory in Salt Lake City"),
                           ("shikun_binui", "proposal price per user"),
                           ("ashtrom_group", "meeting notes and proposals")]:
        for e in search(query, k=10, company_id=company, chroma_dir=kb_dir):
            meta = e["metadata"]
            assert meta["scope"] == "global" or company in (meta["customer_org_id"], meta["subject_org_id"]), \
                (company, e["evidence_id"])


def test_origin_filter(kb_dir):
    results = search("Arup ownership", k=10, company_id="arup", origin="public_source", chroma_dir=kb_dir)
    assert results and all(e["info_origin"] == "public_source" for e in results)


def test_global_only_search_for_unknown_company(kb_dir):
    results = search("recent proposals and meetings", k=10, global_only=True, chroma_dir=kb_dir)
    assert results and all(e["metadata"]["scope"] == "global" for e in results)


def test_evidence_objects_carry_labels_and_resolved_reality(kb_dir):
    for e in search("Engineering Vault proposal for Arup", k=5, company_id="arup", chroma_dir=kb_dir):
        assert e["provenance_label"]
        assert all(o["reality"] in ("real", "fictional") for o in e["organizations"])
        if e["info_origin"] == "synthetic_record" and any(o["reality"] == "real" for o in e["organizations"]):
            assert e["provenance_label"].startswith("SYNTHETIC")


def test_embedding_text_adds_document_context_but_not_provenance_labels():
    chunks = {c["chunk_id"]: c for c in load_kb_chunks()}
    row_2025 = next(c for c in chunks.values()
                    if c["metadata"]["document_id"] == "NVQ-PRC-2025-v1" and "Tier: Business" in c["text"])
    row_2026 = next(c for c in chunks.values()
                    if c["metadata"]["document_id"] == "NVQ-PRC-2026-v1" and "Tier: Business" in c["text"])
    t25, t26 = embedding_text(row_2025), embedding_text(row_2026)
    assert "Price List 2025" in t25 and "superseded price list, effective 2025-10-01 to 2026-09-30" in t25
    assert "Price List 2026" in t26 and "current approved price list, effective 2026-10-01 to present" in t26
    assert t25.endswith(row_2025["text"]) and t26.endswith(row_2026["text"])
    for c in chunks.values():
        text = embedding_text(c)
        assert c["metadata"]["provenance_label"] not in text
        assert "not a real business fact" not in text and "PUBLIC SOURCE ·" not in text


def test_bm25_stems_and_prefers_rare_terms():
    docs = {"prop": "Proposal: Engineering Vault for Shikun & Binui",
            "pub1": "Shikun & Binui company history", "pub2": "Shikun & Binui group structure"}
    assert bm25_rank("What did we propose to Shikun & Binui?", docs)[0] == "prop"
    assert bm25_rank("unrelated words", docs) == []


@pytest.mark.parametrize("name, domain, status, org_id, candidates", [
    ("Arup", None, "ambiguous", None, ["arup", "arup_laboratories"]),
    ("Arup", "arup.com", "resolved", "arup", ["arup"]),
    ("Arup Group", None, "resolved", "arup", ["arup"]),
    ("ARUP Laboratories", None, "resolved", "arup_laboratories", ["arup_laboratories"]),
    ("Shikun and Binui", None, "resolved", "shikun_binui", ["shikun_binui"]),
    ("Shikun & Binui Ltd.", None, "resolved", "shikun_binui", ["shikun_binui"]),
    ("Ashtrom", None, "resolved", "ashtrom_group", ["ashtrom_group"]),
    ("Teva Pharmaceutical", None, "unresolved", None, []),
    ("Nivarque", None, "unresolved", None, []),
])
def test_resolve_company(name, domain, status, org_id, candidates):
    r = resolve_company(name, domain=domain)
    assert (r["status"], r["org_id"], r["candidates"]) == (status, org_id, candidates)
