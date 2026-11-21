"""Prompt 06: SQLite history, meeting notes -> DRAFT -> APPROVED, follow-up tasks, history index and UI.

All offline: simulated notes, the rule-based proposer, the template drafter, local SQLite and Chroma.
Every meeting record is a SYNTHETIC user-entered demonstration record, never a verified fact.
"""
import sqlite3
from pathlib import Path

import pytest

from deal_prep import app_service
from deal_prep.app_service import BriefingService
from deal_prep.history import TASK_STATUSES, HistoryStore, IdempotencyConflict
from deal_prep.history_index import HISTORY_COLLECTION, reconcile, search_history, sync_meeting
from deal_prep.index import _client
from deal_prep.kb_index import build_kb_index
from deal_prep.notes import PROPOSER_LABEL, propose_structure

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"

NOTES = ("Participants: Dana Levi, Omer Katz\n"
         "The customer is concerned about migration effort from their current archive.\n"
         "We agreed to run a pilot with the engineering department.\n"
         "We will send the revised proposal by 30 November 2026.\n"
         "Schedule a security review next week.")
APPROVED = {"summary": "Pilot agreed; migration effort is the main concern.", "participants": ["Dana Levi"],
            "concerns": ["Migration effort from the current archive."], "decisions": ["Run a pilot."],
            "commitments": ["Send the revised proposal."]}


@pytest.fixture()
def store(tmp_path):
    return HistoryStore(tmp_path / "history.sqlite")


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("history_kb")
    build_kb_index(chroma_dir=d)
    return d


def draft(store, company="Shikun & Binui", org="shikun_binui", op="op-1", notes=NOTES):
    cid = store.get_or_create_company(company, org)
    return cid, store.create_meeting_draft(cid, notes, propose_structure(notes), op, "2026-11-02")


def indexed_ids(chroma_dir):
    return set(_client(chroma_dir).get_or_create_collection(HISTORY_COLLECTION, embedding_function=None).get()["ids"])


# --- SQLite store --------------------------------------------------------------------------------

def test_schema_init_is_idempotent_and_foreign_keys_are_enforced(tmp_path):
    path = tmp_path / "h.sqlite"
    HistoryStore(path)
    s = HistoryStore(path)  # second init on the same file
    with s.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        s.create_task("no-such-company", "Call back", "op-x")


def test_company_is_unique_by_org_id_and_by_name(store):
    a = store.get_or_create_company("Shikun & Binui", "shikun_binui")
    assert store.get_or_create_company("Shikun & Binui Ltd", "shikun_binui") == a
    b = store.get_or_create_company("Teva Pharmaceutical")
    assert store.get_or_create_company("  teva   pharmaceutical ") == b == "name:teva pharmaceutical"
    assert len(store.companies()) == 2


def test_meeting_records_are_always_synthetic(store):
    cid, mid = draft(store)
    m = store.meeting(mid)
    assert m["status"] == "DRAFT" and m["info_origin"] == "synthetic_record"
    assert m["creation_method"] == "ai_proposed_from_user_notes"
    with store.connect() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE meetings SET info_origin = 'public_source' WHERE meeting_id = ?", (mid,))
    with pytest.raises(ValueError):
        store.create_meeting_draft(cid, "notes", {}, "op-2", creation_method="curated_snapshot")


def test_meeting_and_task_creation_are_idempotent(store):
    cid, mid = draft(store)
    assert draft(store)[1] == mid  # same operation repeated (double submit, retry)
    with pytest.raises(IdempotencyConflict):
        draft(store, notes=NOTES + " Extra.")  # same operation ID, different payload
    t1 = store.create_task(cid, "Send proposal", "t-op", meeting_id=mid)
    assert store.create_task(cid, "Send proposal", "t-op", meeting_id=mid) == t1
    with pytest.raises(IdempotencyConflict):
        store.create_task(cid, "Something else", "t-op")
    assert len(store.meetings(cid)) == 1 and len(store.tasks(cid)) == 1


def test_task_status_changes_are_recorded_and_validated(store):
    cid = store.get_or_create_company("Ashtrom Group", "ashtrom")
    tid = store.create_task(cid, "Share reference list", "op", due_date="2026-11-20")
    store.set_task_status(tid, "In Progress")
    store.set_task_status(tid, "In Progress")  # unchanged: no extra history row
    store.set_task_status(tid, "Completed")
    assert [h["to_status"] for h in store.task_history(tid)] == ["Open", "In Progress", "Completed"]
    with pytest.raises(ValueError):
        store.set_task_status(tid, "Done")
    with pytest.raises(ValueError):
        store.create_task(cid, "Bad date", "op2", due_date="next Friday")  # only confirmed ISO dates
    assert TASK_STATUSES == ("Open", "In Progress", "Completed")


def test_saved_briefing_snapshot_reopens_unchanged(store):
    cid = store.get_or_create_company("Arup", "arup")
    result = {"run_id": "r1", "created_at": "2026-11-01T09:00:00+00:00", "mode": "baseline",
              "status": "partial_briefing", "briefing": {"company_overview": []}}
    store.save_briefing(cid, result)
    store.save_briefing(cid, {**result, "status": "changed"})  # same run saved again: ignored
    assert store.open_briefing("r1") == result
    assert [b["created_at"] for b in store.briefings(cid)] == ["2026-11-01T09:00:00+00:00"]


# --- proposer ------------------------------------------------------------------------------------

def test_proposer_copies_from_notes_and_invents_nothing():
    p = propose_structure(NOTES)
    assert p["proposer"] == PROPOSER_LABEL
    assert p["participants"] == ["Dana Levi", "Omer Katz"]
    assert p["concerns"] == ["The customer is concerned about migration effort from their current archive."]
    assert p["decisions"] == ["We agreed to run a pilot with the engineering department."]
    for item in p["concerns"] + p["decisions"] + p["commitments"] + [t["description"] for t in p["tasks"]]:
        assert item in NOTES


def test_proposer_suggests_only_explicit_dates_and_keeps_vague_ones_raw():
    tasks = {t["description"]: t for t in propose_structure(NOTES)["tasks"]}
    explicit = tasks["We will send the revised proposal by 30 November 2026."]
    assert explicit["suggested_due_date"] == "2026-11-30" and explicit["needs_confirmation"]
    vague = tasks["Schedule a security review next week."]
    assert vague["suggested_due_date"] is None and vague["due_raw"] == "next week"
    assert any("next week" in u for u in propose_structure(NOTES)["unknowns"])


def test_proposer_lists_missing_participants_as_unknown():
    p = propose_structure("Customer asked about pricing. Send the price list on Friday.")
    assert p["participants"] == [] and "participants not stated in the notes" in p["unknowns"]
    assert p["tasks"][0]["suggested_due_date"] is None and p["tasks"][0]["due_raw"] == "Friday"


# --- history index (approved records only) ---------------------------------------------------------

def test_drafts_are_never_indexed_and_approval_indexes_with_labels(store, tmp_path):
    cid, mid = draft(store)
    sync_meeting(store, mid, tmp_path)
    assert search_history(store, cid, "migration pilot", chroma_dir=tmp_path) == []
    store.approve_meeting(mid, APPROVED)
    sync_meeting(store, mid, tmp_path)
    [hit] = search_history(store, cid, "migration pilot", chroma_dir=tmp_path)
    assert hit["evidence_id"] == f"HIST-{mid}#0" and hit["info_origin"] == "synthetic_record"
    assert hit["provenance_label"].startswith("SYNTHETIC — user-entered demonstration meeting record (2026-11-02")
    assert "not a verified real-world fact" in hit["provenance_label"]
    assert hit["metadata"]["approval_status"] == "approved" and hit["metadata"]["customer_org_id"] == "shikun_binui"
    assert "Pilot agreed" in hit["text"]


def test_edits_and_task_status_resync_the_index(store, tmp_path):
    cid, mid = draft(store)
    store.approve_meeting(mid, APPROVED)
    tid = store.create_task(cid, "Send the revised proposal.", "t", meeting_id=mid, due_raw="next week")
    sync_meeting(store, mid, tmp_path)
    [hit] = search_history(store, cid, "proposal", chroma_dir=tmp_path)
    assert "Follow-up task (Open, due not confirmed ('next week'))" in hit["text"]
    store.approve_meeting(mid, {**APPROVED, "summary": "Edited summary after review."})
    store.set_task_status(tid, "Completed")
    sync_meeting(store, mid, tmp_path)
    [hit] = search_history(store, cid, "proposal", chroma_dir=tmp_path)
    assert "Edited summary after review." in hit["text"] and "Follow-up task (Completed" in hit["text"]
    assert len(indexed_ids(tmp_path)) == 1


def test_history_search_is_company_scoped(store, tmp_path):
    _, a = draft(store)
    other, b = draft(store, "Ashtrom Group", "ashtrom", op="op-b")
    for mid in (a, b):
        store.approve_meeting(mid, APPROVED)
        sync_meeting(store, mid, tmp_path)
    hits = search_history(store, other, "migration pilot", chroma_dir=tmp_path)
    assert [h["metadata"]["meeting_id"] for h in hits] == [b]


def test_reconcile_removes_stale_entries_and_restores_missing_ones(store, tmp_path):
    cid, mid = draft(store)
    store.approve_meeting(mid, APPROVED)
    sync_meeting(store, mid, tmp_path)
    other = HistoryStore(tmp_path / "other.sqlite")  # an entry whose record is not in this database
    ocid, omid = draft(other, op="op-o")
    other.approve_meeting(omid, APPROVED)
    sync_meeting(other, omid, tmp_path)
    _client(tmp_path).get_collection(HISTORY_COLLECTION).delete(ids=[f"HIST-{mid}#0"])  # lost index write
    assert search_history(store, cid, "pilot", chroma_dir=tmp_path) == []  # stale entry is never trusted
    assert reconcile(store, tmp_path) == {"removed": [omid], "indexed": [mid]}
    assert indexed_ids(tmp_path) == {f"HIST-{mid}#0"}


def test_crash_after_sqlite_commit_then_retry_leaves_no_duplicates(tmp_path, monkeypatch):
    service = BriefingService(chroma_dir=tmp_path)
    cid = service.store.get_or_create_company("Shikun & Binui", "shikun_binui")
    mid = service.add_meeting_draft(cid, NOTES, "op-1", "2026-11-02")
    tasks = [{"description": "Send the revised proposal.", "due_date": "2026-11-30", "op_id": f"{mid}:task:0"}]

    def crash(*a, **k):
        raise RuntimeError("simulated crash before the index write")
    real_sync = app_service.sync_meeting
    monkeypatch.setattr(app_service, "sync_meeting", crash)
    with pytest.raises(RuntimeError):
        service.approve_meeting(mid, APPROVED, tasks)
    assert service.store.meeting(mid)["status"] == "APPROVED" and indexed_ids(tmp_path) == set()
    monkeypatch.setattr(app_service, "sync_meeting", real_sync)
    service.approve_meeting(mid, APPROVED, tasks)  # the user retries the same approval
    assert len(service.store.tasks(cid)) == 1 and indexed_ids(tmp_path) == {f"HIST-{mid}#0"}
    assert service.reconcile_history() == {"removed": [], "indexed": [mid]}


# --- end to end: briefing -> notes -> approve -> task -> later briefing -----------------------------

def test_full_sequence_later_briefing_uses_approved_history_only(kb, tmp_path):
    service = BriefingService(chroma_dir=kb, history_path=tmp_path / "e2e.sqlite")
    first, ran = service.get("Shikun & Binui", None, "general")
    assert ran and first["status"] in ("briefing_ready", "partial_briefing")
    cid = first["company_id"]
    assert not any(e.startswith("HIST-") for e in first["evidence_ids"])

    mid = service.add_meeting_draft(cid, NOTES, "op-1", "2026-11-02")
    service.add_meeting_draft(cid, "Draft only: zebrafish integration was mentioned.", "op-2")
    assert service.get("Shikun & Binui", None, "general")[1] is False  # drafts do not change anything

    [task_id] = service.approve_meeting(mid, APPROVED, [{"description": "Send the revised proposal.",
                                                         "due_date": "2026-11-30", "op_id": f"{mid}:task:0"}])
    second, ran = service.get("Shikun & Binui", None, "general")
    assert ran
    hist = second["evidence"][f"HIST-{mid}#0"]
    assert hist["source"] == "internal:meeting_history" and hist["info_origin"] == "synthetic_record"
    assert hist["provenance_label"].startswith("SYNTHETIC — user-entered demonstration meeting record")
    assert not any("zebrafish" in e["excerpt"] for e in second["evidence"].values())
    items = [i for i in second["briefing"]["our_relationship"] if f"HIST-{mid}#0" in i["evidence_ids"]]
    assert items and items[0]["claim_type"] == "meeting_history"
    assert items[0]["text"].startswith("Past meeting (synthetic user-entered demonstration record, not a verified fact)")

    service.set_task_status(task_id, "Completed")
    third, ran = service.get("Shikun & Binui", None, "general")
    assert ran and "Follow-up task (Completed" in third["evidence"][f"HIST-{mid}#0"]["excerpt"]

    saved = service.store.briefings(cid)
    assert len(saved) == 3
    assert service.store.open_briefing(first["run_id"])["created_at"] == first["created_at"]  # snapshot unchanged


def test_unregistered_company_with_approved_history_has_no_internal_gap(kb, tmp_path):
    service = BriefingService(chroma_dir=kb, history_path=tmp_path / "u.sqlite")
    cid = service.company_id_for("Teva Pharmaceutical")
    mid = service.add_meeting_draft(cid, NOTES, "op-1", "2026-11-02")
    service.approve_meeting(mid, APPROVED)
    result, _ = service.get("Teva Pharmaceutical", None, "general")
    assert f"HIST-{mid}#0" in result["evidence"]
    assert result["status"] in ("briefing_ready", "partial_briefing")


# --- Streamlit tabs (headless) ---------------------------------------------------------------

def test_streamlit_history_and_tasks_tabs(kb, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("DEAL_PREP_APP_CHROMA_DIR", str(kb))
    monkeypatch.setenv("DEAL_PREP_HISTORY_DB", str(tmp_path / "ui.sqlite"))
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")  # tests never read .env
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Prepare Meeting", "Meeting History", "Follow-up Tasks"]

    at.selectbox(key="history_company").set_value("Ashtrom Group")
    next(t for t in at.text_area if t.label == "Free-text notes").set_value(NOTES)
    next(b for b in at.button if b.label.startswith("Propose structure")).click().run()
    assert not at.exception
    store = at.session_state.service.store
    cid = at.session_state.service.company_id_for("Ashtrom Group")
    [m] = store.meetings(cid)
    assert m["status"] == "DRAFT"
    assert any("SYNTHETIC" in md.value and "not a verified real-world fact" in md.value for md in at.markdown)

    at.checkbox(key=f"mk_{m['meeting_id']}_0").check()
    next(b for b in at.button if b.label == "Approve this record").click().run()
    assert not at.exception and store.meeting(m["meeting_id"])["status"] == "APPROVED"
    [task] = store.tasks(cid)
    assert task["due_date"] == "2026-11-30" and task["status"] == "Open"

    at.selectbox(key="tasks_company").set_value("Ashtrom Group").run()
    at.selectbox(key=f"status_{task['task_id']}").set_value("Completed").run()
    assert not at.exception and store.tasks(cid)[0]["status"] == "Completed"
