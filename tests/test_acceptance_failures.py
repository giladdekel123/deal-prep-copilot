"""Prompt 07 step 3: deliberate failure modes, offline (inconsistent local index, corrupted documents,
shared company context).

The three defects found by the audit were first recorded as strict xfail tests. Each marker was removed
only after the approved fix made the test pass unexpectedly (XPASS(strict)) on 2026-11-06; the tests now
guard against regressions. No assertion was weakened.
"""
import shutil
from pathlib import Path

import pytest

from deal_prep import kb_index
from deal_prep.app_service import BriefingService
from deal_prep.index import _client
from deal_prep.kb_index import KB_COLLECTION, build_kb_index, load_kb_chunks, load_manifest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_missing_kb_index_is_rebuilt_and_briefing_recovers(tmp_path):
    service = BriefingService(chroma_dir=tmp_path)  # no collection exists yet
    result, ran = service.get("Shikun & Binui", None, "general")
    assert ran and result["status"] == "partial_briefing" and result["evidence_ids"]
    assert _client(tmp_path).get_collection(KB_COLLECTION).count() > 0


def empty_index_result(tmp_path):
    _client(tmp_path).create_collection(KB_COLLECTION, embedding_function=None, metadata={"hnsw:space": "cosine"})
    return BriefingService(chroma_dir=tmp_path).get("Shikun & Binui", None, "general")[0]


def test_empty_kb_index_never_produces_an_invented_briefing(tmp_path):
    # Expectation changed by the approved index-repair fix (2026-11-06): an empty index used to give no briefing;
    # it is now rebuilt first, so the briefing must rest only on real corpus passages from a complete index.
    result = empty_index_result(tmp_path)
    corpus_ids = {c["chunk_id"] for c in load_kb_chunks()}
    assert _client(tmp_path).get_collection(KB_COLLECTION).count() == len(corpus_ids)
    assert result["status"] == "partial_briefing" and result["evidence_ids"]  # offline: news is off
    assert set(result["evidence_ids"]) <= corpus_ids


def test_empty_kb_index_is_reported_as_an_index_problem(tmp_path):
    result = empty_index_result(tmp_path)
    assert "index" in result["message"].lower()
    assert "No prior relationship records" not in result["message"]


def corrupt_corpus(tmp_path, monkeypatch) -> dict:
    """Point the knowledge base at a copy of data/kb_v1 whose spreadsheet is replaced by non-spreadsheet bytes."""
    corpus = tmp_path / "kb_v1"
    shutil.copytree(kb_index.KB_DIR, corpus)
    doc = next(d for d in load_manifest() if d["file_type"] == "xlsx")
    (corpus / doc["file_path"]).write_bytes(b"\x00\x01 not a spreadsheet \xff")
    monkeypatch.setattr(kb_index, "KB_DIR", corpus)
    return doc


def test_corrupted_document_stops_the_build_and_keeps_the_existing_index(tmp_path, monkeypatch):
    chroma = tmp_path / "chroma"
    build_kb_index(chroma_dir=chroma)  # a good index already exists
    before = _client(chroma).get_collection(KB_COLLECTION).count()
    corrupt_corpus(tmp_path, monkeypatch)
    with pytest.raises(Exception):
        build_kb_index(chroma_dir=chroma)
    assert _client(chroma).get_collection(KB_COLLECTION).count() == before  # old index untouched


def test_corrupted_document_error_names_the_document(tmp_path, monkeypatch):
    doc = corrupt_corpus(tmp_path, monkeypatch)
    with pytest.raises(Exception) as err:
        build_kb_index(chroma_dir=tmp_path / "chroma")
    assert doc["document_id"] in str(err.value)


def test_company_context_is_shared_across_pages(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    chroma = tmp_path / "chroma"
    build_kb_index(chroma_dir=chroma)
    monkeypatch.setenv("DEAL_PREP_APP_CHROMA_DIR", str(chroma))
    monkeypatch.setenv("DEAL_PREP_HISTORY_DB", str(tmp_path / "ui.sqlite"))
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")  # tests never read .env
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    at.selectbox[0].set_value("Arup")  # Prepare Meeting company
    next(b for b in at.button if b.label.startswith("Prepare briefing")).click().run()
    assert not at.exception
    assert at.selectbox(key="history_company").value == "Arup"
    assert at.selectbox(key="tasks_company").value == "Arup"
    at.selectbox(key="history_company").set_value("Ashtrom Group").run()  # changed on Meeting History
    assert not at.exception
    assert at.selectbox(key="tasks_company").value == "Ashtrom Group"
