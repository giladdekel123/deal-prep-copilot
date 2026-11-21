"""SQLite source of truth for Stage 2 (Prompt 06; spec FR-12–FR-15, §6B, §7, AT-12–AT-15, AT-21).

Tables: companies (reference Organization by org_id; no duplicated identity fields), dated briefing
snapshots, meeting records (DRAFT -> APPROVED), follow-up tasks and their status history.
- Every meeting record is info_origin=synthetic_record (user-entered demonstration data): it is never
  a verified real-world fact. creation_method is user_entered_demo or ai_proposed_from_user_notes.
- Creating a meeting or a task takes a stable operation ID (idempotency key). Repeating the same
  operation returns the existing record; reusing an ID with a different payload is refused.
- All writes are single transactions; foreign keys are enforced.
- A saved briefing snapshot is never refreshed: reopening returns exactly what was saved.
"""
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from deal_prep import config

DB_PATH = Path(os.environ.get("DEAL_PREP_HISTORY_DB", config.PROJECT_ROOT / "runs" / "history.sqlite"))
TASK_STATUSES = ("Open", "In Progress", "Completed")
CREATION_METHODS = {"user_entered_demo", "ai_proposed_from_user_notes"}
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY, org_id TEXT UNIQUE, name_key TEXT UNIQUE NOT NULL,
    input_name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS briefings (
    briefing_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
    created_at TEXT NOT NULL, saved_at TEXT NOT NULL, mode TEXT, status TEXT, snapshot_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meetings (
    meeting_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
    meeting_date TEXT, raw_notes TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'APPROVED')),
    info_origin TEXT NOT NULL CHECK (info_origin = 'synthetic_record'),
    creation_method TEXT NOT NULL, proposed_json TEXT NOT NULL, approved_json TEXT, approved_at TEXT,
    created_at TEXT NOT NULL, op_id TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
    meeting_id TEXT REFERENCES meetings(meeting_id), description TEXT NOT NULL,
    due_date TEXT, due_raw TEXT,
    status TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Completed')),
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, op_id TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(task_id),
    from_status TEXT, to_status TEXT NOT NULL, changed_at TEXT NOT NULL);
"""


class IdempotencyConflict(ValueError):
    """The operation ID was already used for a different payload."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def name_key(name: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", name.casefold().replace("&", " and ")).split())


def _iso_date(value):
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value)).isoformat()  # raises on anything that is not a real date


class HistoryStore:
    def __init__(self, path: Path | str = DB_PATH):
        from deal_prep.public_demo import require_not_public
        require_not_public("The meeting-history and task database")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        from deal_prep.public_demo import require_not_public
        require_not_public("The meeting-history and task database")
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            if conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

    # --- companies -------------------------------------------------------------------------

    def get_or_create_company(self, name: str, org_id: str | None = None) -> str:
        """Company references the Organization registry by org_id; identity is not copied here."""
        key = name_key(name)
        if not key:
            raise ValueError("company name is required")
        with self.connect() as conn:
            row = conn.execute("SELECT company_id FROM companies WHERE (org_id IS NOT NULL AND org_id = ?) "
                               "OR name_key = ?", (org_id, key)).fetchone()
            if row:
                return row["company_id"]
            company_id = org_id or f"name:{key}"
            conn.execute("INSERT INTO companies VALUES (?, ?, ?, ?, ?)",
                         (company_id, org_id, key, name.strip(), _now()))
            return company_id

    def companies(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY input_name")]

    def company(self, company_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,)).fetchone()
            return dict(row) if row else None

    # --- briefing snapshots ----------------------------------------------------------------------

    def save_briefing(self, company_id: str, result: dict) -> str:
        """Store a dated snapshot once (keyed by run ID). Saving the same run again changes nothing."""
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO briefings VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (result["run_id"], company_id, result["created_at"], _now(), result.get("mode"),
                          result.get("status"), json.dumps(result, ensure_ascii=False, default=str)))
        return result["run_id"]

    def briefings(self, company_id: str) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT briefing_id, created_at, saved_at, mode, status FROM briefings WHERE company_id = ? "
                "ORDER BY created_at DESC", (company_id,))]

    def open_briefing(self, briefing_id: str) -> dict:
        """Exactly the saved snapshot, never re-researched."""
        with self.connect() as conn:
            row = conn.execute("SELECT snapshot_json FROM briefings WHERE briefing_id = ?", (briefing_id,)).fetchone()
        if not row:
            raise KeyError(briefing_id)
        return json.loads(row["snapshot_json"])

    # --- meetings --------------------------------------------------------------------------------

    def create_meeting_draft(self, company_id: str, raw_notes: str, proposal: dict, op_id: str,
                             meeting_date: str | None = None,
                             creation_method: str = "ai_proposed_from_user_notes") -> str:
        if not raw_notes.strip():
            raise ValueError("meeting notes are required")
        if creation_method not in CREATION_METHODS:
            raise ValueError(f"creation_method must be one of {sorted(CREATION_METHODS)}")
        meeting_date = _iso_date(meeting_date)
        payload = {"company_id": company_id, "raw_notes": raw_notes, "meeting_date": meeting_date,
                   "proposal": proposal, "creation_method": creation_method}
        h = _hash(payload)
        with self.connect() as conn:
            row = conn.execute("SELECT meeting_id, payload_hash FROM meetings WHERE op_id = ?", (op_id,)).fetchone()
            if row:
                if row["payload_hash"] != h:
                    raise IdempotencyConflict(f"operation {op_id} was already used for a different meeting")
                return row["meeting_id"]
            meeting_id = f"MTG-{uuid.uuid4().hex[:10]}"
            conn.execute("INSERT INTO meetings (meeting_id, company_id, meeting_date, raw_notes, status, info_origin, "
                         "creation_method, proposed_json, created_at, op_id, payload_hash) "
                         "VALUES (?, ?, ?, ?, 'DRAFT', 'synthetic_record', ?, ?, ?, ?, ?)",
                         (meeting_id, company_id, meeting_date, raw_notes, creation_method,
                          json.dumps(proposal, ensure_ascii=False), _now(), op_id, h))
            return meeting_id

    def approve_meeting(self, meeting_id: str, approved: dict) -> None:
        """Explicit human approval (or re-approval after an edit). Only APPROVED records influence briefings."""
        with self.connect() as conn:
            cur = conn.execute("UPDATE meetings SET status = 'APPROVED', approved_json = ?, approved_at = ? "
                               "WHERE meeting_id = ?", (json.dumps(approved, ensure_ascii=False), _now(), meeting_id))
            if cur.rowcount != 1:
                raise KeyError(meeting_id)

    def meeting(self, meeting_id: str) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM meetings WHERE meeting_id = ?", (meeting_id,)).fetchone()
        if not row:
            raise KeyError(meeting_id)
        return self._meeting_dict(row)

    def meetings(self, company_id: str, status: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM meetings WHERE company_id = ?", [company_id]
        if status:
            sql, args = sql + " AND status = ?", args + [status]
        with self.connect() as conn:
            return [self._meeting_dict(r) for r in conn.execute(sql + " ORDER BY created_at DESC", args)]

    def approved_meetings(self) -> list[dict]:
        with self.connect() as conn:
            return [self._meeting_dict(r) for r in conn.execute("SELECT * FROM meetings WHERE status = 'APPROVED'")]

    @staticmethod
    def _meeting_dict(row) -> dict:
        d = dict(row)
        d["proposed"] = json.loads(d.pop("proposed_json"))
        d["approved"] = json.loads(d.pop("approved_json")) if d["approved_json"] else None
        d.pop("payload_hash")
        return d

    # --- tasks -------------------------------------------------------------------------------------

    def create_task(self, company_id: str, description: str, op_id: str, meeting_id: str | None = None,
                    due_date: str | None = None, due_raw: str | None = None) -> str:
        """due_date must be a confirmed ISO date (or None); a vague expression stays in due_raw only."""
        if not description.strip():
            raise ValueError("task description is required")
        due_date = _iso_date(due_date)
        payload = {"company_id": company_id, "description": description.strip(), "meeting_id": meeting_id,
                   "due_date": due_date, "due_raw": due_raw}
        h = _hash(payload)
        now = _now()
        with self.connect() as conn:
            row = conn.execute("SELECT task_id, payload_hash FROM tasks WHERE op_id = ?", (op_id,)).fetchone()
            if row:
                if row["payload_hash"] != h:
                    raise IdempotencyConflict(f"operation {op_id} was already used for a different task")
                return row["task_id"]
            task_id = f"TSK-{uuid.uuid4().hex[:10]}"
            conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?)",
                         (task_id, company_id, meeting_id, description.strip(), due_date, due_raw, now, now, op_id, h))
            conn.execute("INSERT INTO task_status_history (task_id, from_status, to_status, changed_at) "
                         "VALUES (?, NULL, 'Open', ?)", (task_id, now))
            return task_id

    def set_task_status(self, task_id: str, status: str) -> None:
        if status not in TASK_STATUSES:
            raise ValueError(f"status must be one of {TASK_STATUSES}")
        with self.connect() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                raise KeyError(task_id)
            if row["status"] == status:
                return  # no change, no history entry
            now = _now()
            conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", (status, now, task_id))
            conn.execute("INSERT INTO task_status_history (task_id, from_status, to_status, changed_at) "
                         "VALUES (?, ?, ?, ?)", (task_id, row["status"], status, now))

    def tasks(self, company_id: str | None = None, meeting_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM tasks WHERE 1 = 1", []
        if company_id:
            sql, args = sql + " AND company_id = ?", args + [company_id]
        if meeting_id:
            sql, args = sql + " AND meeting_id = ?", args + [meeting_id]
        with self.connect() as conn:
            return [{k: v for k, v in dict(r).items() if k != "payload_hash"}
                    for r in conn.execute(sql + " ORDER BY created_at", args)]

    def task_history(self, task_id: str) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT from_status, to_status, changed_at FROM task_status_history WHERE task_id = ? ORDER BY id",
                (task_id,))]

    def version(self, company_id: str) -> str:
        """Changes whenever approved history or task state for the company changes (for cache keys)."""
        with self.connect() as conn:
            m = conn.execute("SELECT COUNT(*), MAX(approved_at) FROM meetings WHERE company_id = ? AND "
                             "status = 'APPROVED'", (company_id,)).fetchone()
            t = conn.execute("SELECT COUNT(*), MAX(updated_at) FROM tasks WHERE company_id = ?", (company_id,)).fetchone()
        return f"{m[0]}:{m[1]}:{t[0]}:{t[1]}"
