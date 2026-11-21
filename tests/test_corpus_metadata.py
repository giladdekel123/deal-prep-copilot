from datetime import date

import pytest

from deal_prep import config
from deal_prep.corpus import (REQUIRED_FIELDS, CorpusPathError, UnsupportedFormatError,
                              extract_text, resolve_document_path)


def test_manifest_and_files_match_one_to_one(manifest):
    listed = {d["file_path"] for d in manifest}
    on_disk = {p.name for p in config.DMS_CORPUS_DIR.iterdir() if p.name != "manifest.json"}
    assert listed == on_disk


def test_corpus_size_is_3_to_5(manifest):
    assert 3 <= len(manifest) <= 5


def test_required_fields_present(manifest):
    for doc in manifest:
        missing = [f for f in REQUIRED_FIELDS if f not in doc]
        assert not missing, f"{doc.get('document_id')}: missing {missing}"
        assert doc["title"] and doc["document_id"] and doc["source_type"]


def test_document_ids_unique(manifest):
    ids = [d["document_id"] for d in manifest]
    assert len(ids) == len(set(ids))


def test_every_document_labelled_synthetic(manifest):
    for doc in manifest:
        assert doc["source_label"] == "synthetic"
        text = extract_text(resolve_document_path(doc))
        assert "SYNTHETIC" in "\n".join(text.splitlines()[:3]), doc["document_id"]


def test_file_type_matches_extension(manifest):
    for doc in manifest:
        assert doc["file_path"].lower().endswith("." + doc["file_type"])


def test_dates_valid_and_ordered(manifest):
    for doc in manifest:
        issued = date.fromisoformat(doc["issued_at"])
        start = date.fromisoformat(doc["effective_from"])
        assert issued <= start
        if doc["effective_to"] is not None:
            assert start <= date.fromisoformat(doc["effective_to"])


def test_approval_status_vocabulary(manifest):
    assert {d["approval_status"] for d in manifest} <= {"approved", "draft", "superseded"}


def test_metadata_preserved_in_every_chunk(manifest, chunks):
    by_id = {d["document_id"]: d for d in manifest}
    assert {c["document_id"] for c in chunks} == set(by_id)
    for c in chunks:
        doc = by_id[c["document_id"]]
        for field in REQUIRED_FIELDS:
            expected = "" if doc[field] is None else doc[field]
            assert c["metadata"][field] == expected, (c["chunk_id"], field)


def test_chunk_ids_unique_and_stable(chunks):
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(cid.startswith(c["document_id"] + "#") for cid, c in zip(ids, chunks))


@pytest.mark.parametrize("ext", ["pdf", "docx", "xlsx"])
def test_unimplemented_formats_raise(tmp_path, ext):
    f = tmp_path / f"sample.{ext}"
    f.write_bytes(b"x")
    with pytest.raises(UnsupportedFormatError, match="not implemented until Prompt 02"):
        extract_text(f)


def test_path_outside_corpus_refused():
    with pytest.raises(CorpusPathError):
        resolve_document_path({"document_id": "X", "file_path": "../../../classroom/nexastream/x.md"})
