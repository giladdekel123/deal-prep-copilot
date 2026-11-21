"""Phase 4.5 I1: structured meeting history reaches the briefing writer complete and current.

All offline: local SQLite and Chroma, simulated records. Every meeting record is a SYNTHETIC user-entered
demonstration record, never a verified fact.
"""
import pytest

from deal_prep.evidence import EXCERPT_WORDS, MEETING_MAX_TASKS, meeting_excerpt, normalize
from deal_prep.history import HistoryStore
from deal_prep.history_index import meeting_text, search_history, sync_meeting

LONG = {"summary": " ".join(["The customer reviewed the proposal in detail."] * 15),  # about 105 words
        "participants": ["Operations director", "Account executive"],
        "concerns": ["Migration effort from the current archive."], "decisions": ["Run a pilot."],
        "commitments": ["Send the revised proposal by 30 November 2026."]}


@pytest.fixture()
def store(tmp_path):
    return HistoryStore(tmp_path / "history.sqlite")


def approved_meeting(store, approved=LONG, tasks=(("Send the revised proposal", "2026-11-30"),
                                                  ("Share the migration checklist", "2026-11-20"))):
    cid = store.get_or_create_company("Zentoy Works", None)
    mid = store.create_meeting_draft(cid, "notes", {}, "op-m", "2026-11-02")
    store.approve_meeting(mid, approved)
    tids = [store.create_task(cid, d, f"op-t{i}", meeting_id=mid, due_date=due) for i, (d, due) in enumerate(tasks)]
    return cid, mid, tids


def test_long_meeting_record_keeps_every_task_with_status_and_due_date(store):
    cid, mid, tids = approved_meeting(store)
    store.set_task_status(tids[1], "Completed")
    text = meeting_text(store.meeting(mid), store.tasks(meeting_id=mid))
    assert len(text.split()) > EXCERPT_WORDS  # the old 60-word excerpt would have cut the tasks off
    ex = meeting_excerpt(text)
    assert "Follow-up task (Open, due 2026-11-30): Send the revised proposal" in ex
    assert "Follow-up task (Completed, due 2026-11-20): Share the migration checklist" in ex
    assert "Commitments: Send the revised proposal by 30 November 2026." in ex


def test_more_tasks_than_shown_are_stated_never_silently_dropped():
    lines = ["Meeting record (2026-11-02): short."] + [f"Follow-up task (Open, due none): Task {i}"
                                                       for i in range(MEETING_MAX_TASKS + 3)]
    ex = meeting_excerpt("\n".join(lines))
    assert ex.count("Follow-up task") == MEETING_MAX_TASKS and "[3 further follow-up tasks not shown]" in ex


def test_only_approved_meeting_records_get_the_structured_excerpt():
    long = " ".join(["word"] * 200)
    kb = normalize({"evidence_id": "NVQ-X#0", "info_origin": "public_source", "provenance_label": "p",
                    "text": long, "metadata": {"doc_type": "company_profile"}}, "internal:company_profile")
    assert len(kb["excerpt"].split()) == EXCERPT_WORDS + 1  # 60 words plus the ellipsis, unchanged
    draft = normalize({"evidence_id": "HIST-x#0", "info_origin": "synthetic_record", "provenance_label": "p",
                       "text": long, "metadata": {"doc_type": "meeting_record", "approval_status": "draft"}}, "x")
    assert len(draft["excerpt"].split()) == EXCERPT_WORDS + 1


def test_current_task_status_wins_over_a_stale_index_copy(store, tmp_path):
    cid, mid, tids = approved_meeting(store)
    sync_meeting(store, mid, tmp_path)
    store.set_task_status(tids[0], "Completed")  # deliberately NOT re-synced: the index copy still says Open
    [hit] = search_history(store, cid, "revised proposal", chroma_dir=tmp_path)
    ex = normalize(hit, "internal:meeting_history")["excerpt"]
    assert "Follow-up task (Completed, due 2026-11-30): Send the revised proposal" in ex
    assert "(Open, due 2026-11-30)" not in ex
    assert ex.startswith("Meeting record (2026-11-02)") and "SYNTHETIC" in hit["provenance_label"]


def test_offline_template_meeting_item_fits_the_briefing_item_limit_and_keeps_tasks(store):
    from deal_prep import demo
    from deal_prep.briefing import Item
    limit = next(m.max_length for m in Item.model_fields["text"].metadata if hasattr(m, "max_length"))
    assert demo.ITEM_MAX_CHARS == limit
    long = {**LONG, "concerns": [" ".join(["Concern about migration and adoption."] * 8)],
            "decisions": [" ".join(["Decision to run a pilot on two sites."] * 8)]}
    _, mid, tids = approved_meeting(store, approved=long)
    store.set_task_status(tids[1], "Completed")
    ex = meeting_excerpt(meeting_text(store.meeting(mid), store.tasks(meeting_id=mid)))
    text = demo.PREFIXES["meeting_history"] + demo.meeting_summary(ex)
    assert len(text) <= limit
    assert "Send the revised proposal (Open, due 2026-11-30)" in text
    assert "Share the migration checklist (Completed, due 2026-11-20)" in text
    assert "omitted here for length" in text


# --- I1 completion: eligibility from SQLite, newest first, structured fields ----------------------------

def _meeting(store, cid, date, summary, tasks=(), approve=True, op=None):
    op = op or f"op-{cid}-{date}-{summary[:8]}"
    mid = store.create_meeting_draft(cid, f"notes {summary}", {}, op, date)
    if approve:
        store.approve_meeting(mid, {"summary": summary, "participants": ["Buyer"],
                                    "decisions": [f"Decision {date}"], "commitments": [f"Commitment {date}"]})
    tids = [store.create_task(cid, d, f"{op}-t{i}", meeting_id=mid, due_date=due) for i, (d, due, _) in enumerate(tasks)]
    for tid, (_, _, status) in zip(tids, tasks):
        if status != "Open":
            store.set_task_status(tid, status)
    return mid


@pytest.fixture()
def busy_customer(store):
    """Seven approved meetings over a year, two drafts, changed statuses, and another company's records."""
    cid = store.get_or_create_company("Zentoy Works", None)
    other = store.get_or_create_company("Other Co", None)
    ids = {"old_open": _meeting(store, cid, "2025-11-03", "Kick-off; security questionnaire promised",
                                [("Return the security questionnaire", "2025-12-01", "Open")])}
    for i, date in enumerate(("2026-02-10", "2026-04-15", "2026-06-20", "2026-08-25", "2026-09-30")):
        ids[f"done{i}"] = _meeting(store, cid, date, f"Review {i}", [(f"Send summary {i}", date, "Completed")])
    ids["newest"] = _meeting(store, cid, "2026-10-28", "Pricing review",
                             [("Send the revised quote", "2026-11-14", "In Progress"),
                              ("Book the pilot workshop", "2026-11-20", "Completed")])
    ids["draft"] = _meeting(store, cid, "2026-11-01", "DRAFT ONLY confidential idea", approve=False)
    ids["other"] = _meeting(store, other, "2026-11-02", "Other company meeting", [("Other task", None, "Open")])
    return cid, ids


def test_history_eligibility_comes_from_sqlite_newest_first_and_keeps_old_open_commitments(store, busy_customer):
    from deal_prep.history_index import MAX_MEETINGS, company_history
    cid, ids = busy_customer
    hist = company_history(store, cid)
    got = [e["record"]["meeting_id"] for e in hist]
    assert len(got) == MAX_MEETINGS == 5
    assert got[0] == ids["newest"] and ids["old_open"] in got  # a year-old unresolved commitment is not lost
    assert ids["draft"] not in got and ids["other"] not in got
    dates = [e["record"]["meeting_date"] for e in hist]
    assert dates == sorted(dates, reverse=True)  # newest first
    assert hist[0]["record"]["omissions"] == ["2 older approved meeting records are not shown "
                                              "(none of them has an open task)"]
    assert {ids["done0"], ids["done1"]}.isdisjoint(got)  # the two oldest meetings without open tasks give way


def test_structured_record_has_identity_approval_and_current_task_status(store, busy_customer):
    from deal_prep.history_index import company_history
    cid, ids = busy_customer
    rec = company_history(store, cid)[0]
    r = rec["record"]
    assert r["meeting_id"] == ids["newest"] and r["meeting_date"] == "2026-10-28" and r["approval_status"] == "approved"
    assert r["decisions"] == ["Decision 2026-10-28"] and r["commitments"] == ["Commitment 2026-10-28"]
    assert r["follow_up_tasks"] == [
        {"description": "Send the revised quote", "status": "In Progress", "due_date": "2026-11-14"},
        {"description": "Book the pilot workshop", "status": "Completed", "due_date": "2026-11-20"}]
    tid = next(t["task_id"] for t in store.tasks(meeting_id=ids["newest"]) if t["description"] == "Send the revised quote")
    store.set_task_status(tid, "Completed")  # a status change is visible at once (no index involved)
    assert company_history(store, cid)[0]["record"]["follow_up_tasks"][0]["status"] == "Completed"
    assert "SYNTHETIC" in rec["provenance_label"] and rec["metadata"]["approval_status"] == "approved"
    assert rec["info_origin"] == "synthetic_record" and rec["evidence_id"] == f"HIST-{ids['newest']}#0"


def test_more_open_meetings_than_the_limit_are_stated(store):
    from deal_prep.history_index import company_history
    cid = store.get_or_create_company("Zentoy Works", None)
    for i in range(7):
        _meeting(store, cid, f"2026-0{i + 1}-05", f"Meeting {i}", [(f"Task {i}", None, "Open")])
    hist = company_history(store, cid)
    assert len(hist) == 5 and hist[0]["record"]["omissions"] == [
        "2 older approved meeting records are not shown (2 of them with open tasks)"]


def test_the_drafter_and_agent_receive_the_structured_record(store, busy_customer):
    import json
    from deal_prep.agent import agent_context
    from deal_prep.evidence import evidence_index
    from deal_prep.history_index import company_history
    cid, ids = busy_customer
    bundle = {"identity": {"name": "Zentoy Works"}, "purpose": "follow_up", "status": "complete", "gaps": [],
              "internal": {"meeting_history": {"sections": ["our_relationship"], "evidence": company_history(store, cid)}}}
    shown = evidence_index(bundle)[f"HIST-{ids['newest']}#0"]
    assert shown["meeting_record"]["follow_up_tasks"][0]["status"] == "In Progress"
    assert "Follow-up task (In Progress, due 2026-11-14): Send the revised quote" in shown["excerpt"]
    ctx = json.dumps(agent_context(bundle, [], 3))
    assert '"follow_up_tasks"' in ctx and "DRAFT ONLY" not in ctx and "Other company meeting" not in ctx


def test_the_app_service_uses_sqlite_history_not_a_semantic_top_k(tmp_path):
    from deal_prep.app_service import BriefingService
    service = BriefingService(chroma_dir=tmp_path / "chroma", history_path=tmp_path / "history.sqlite")
    cid = service.store.get_or_create_company("Zentoy Works", None)
    for i in range(4):  # four approved meetings: the old semantic search returned at most three
        mid = service.add_meeting_draft(cid, f"notes {i}", f"op-{i}", f"2026-0{i + 1}-10")
        service.approve_meeting(mid, {"summary": f"Meeting {i}"}, [])
    assert len(service.history_search(cid)({"name": "Zentoy Works"})) == 4


def test_drafts_never_reach_the_writer_and_nothing_is_invented(store, tmp_path):
    cid = store.get_or_create_company("Zentoy Works", None)
    mid = store.create_meeting_draft(cid, "DRAFT ONLY secret notes", {}, "op-d", "2026-11-03")
    sync_meeting(store, mid, tmp_path)
    assert search_history(store, cid, "secret notes", chroma_dir=tmp_path) == []
    _, mid2, _ = approved_meeting(store, approved={"summary": "Short."}, tasks=())
    sync_meeting(store, mid2, tmp_path)
    [hit] = search_history(store, cid, "short", chroma_dir=tmp_path)
    ex = normalize(hit, "internal:meeting_history")["excerpt"]
    assert ex == "Meeting record (2026-11-02): Short."  # no participants, decisions or tasks are made up
