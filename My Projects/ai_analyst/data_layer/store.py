"""SQLite store shared by the Streamlit app and the Inngest worker.

Why a database at all? The UI and the worker are separate processes (and,
with docker-compose, separate containers). The UI writes a request, the
worker writes progress events and the final result, and the UI polls them.
The same tables keep the chat history and your 👍/👎 feedback.

SQLite is enough: one file on a shared volume, no server, and WAL mode lets
one writer and several readers work at the same time.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal, Optional

from pydantic import BaseModel

from core.config import settings

Status = Literal["queued", "running", "done", "failed", "cancelled"]
FINAL_STATUSES = ("done", "failed", "cancelled")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    title       TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    request_id  TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    question    TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT,
    result_json TEXT,
    error       TEXT,
    event_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id, created_at);
CREATE TABLE IF NOT EXISTS request_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  TEXT NOT NULL,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_request ON request_events(request_id, id);
CREATE TABLE IF NOT EXISTS feedback (
    request_id  TEXT PRIMARY KEY,
    rating      INTEGER NOT NULL,        -- 1 = 👍, -1 = 👎
    comment     TEXT,
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Request(BaseModel):
    request_id: str
    session_id: str
    question: str
    status: Status
    created_at: str
    finished_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    event_id: Optional[str] = None
    rating: Optional[int] = None

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATUSES


class Session(BaseModel):
    session_id: str
    dataset_id: str
    title: Optional[str] = None
    created_at: str


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or settings.data_dir / "analyst.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # A short-lived connection per operation: safe across threads and processes.
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- sessions ---------------------------------------------------------- #
    def create_session(self, dataset_id: str, title: str | None = None) -> Session:
        s = Session(session_id=uuid.uuid4().hex, dataset_id=dataset_id, title=title, created_at=_now())
        with self._conn() as c:
            c.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)",
                      (s.session_id, s.dataset_id, s.title, s.created_at))
        return s

    def list_sessions(self, dataset_id: str | None = None) -> list[Session]:
        sql, args = "SELECT * FROM sessions", ()
        if dataset_id:
            sql, args = sql + " WHERE dataset_id = ?", (dataset_id,)
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [Session(**dict(r)) for r in rows]

    def set_session_title(self, session_id: str, title: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (title, session_id))

    # ---- requests ---------------------------------------------------------- #
    def create_request(self, session_id: str, question: str) -> Request:
        r = Request(request_id=uuid.uuid4().hex, session_id=session_id, question=question,
                    status="queued", created_at=_now())
        with self._conn() as c:
            c.execute("INSERT INTO requests (request_id, session_id, question, status, created_at) "
                      "VALUES (?, ?, ?, ?, ?)",
                      (r.request_id, r.session_id, r.question, r.status, r.created_at))
        return r

    def set_event_id(self, request_id: str, event_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE requests SET event_id = ? WHERE request_id = ?", (event_id, request_id))

    def mark_running(self, request_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE requests SET status = 'running' WHERE request_id = ? AND status = 'queued'",
                      (request_id,))

    def finish_request(self, request_id: str, status: Status, result: dict | None = None,
                       error: str | None = None) -> None:
        """Only the first final status wins: a late result can't overwrite a cancel."""
        with self._conn() as c:
            c.execute(
                "UPDATE requests SET status = ?, result_json = ?, error = ?, finished_at = ? "
                "WHERE request_id = ? AND status NOT IN ('done', 'failed', 'cancelled')",
                (status, json.dumps(result) if result is not None else None, error, _now(), request_id))

    def get_request(self, request_id: str) -> Request | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT r.*, f.rating FROM requests r LEFT JOIN feedback f USING (request_id) "
                "WHERE r.request_id = ?", (request_id,)).fetchone()
        return self._to_request(row) if row else None

    def list_requests(self, session_id: str) -> list[Request]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT r.*, f.rating FROM requests r LEFT JOIN feedback f USING (request_id) "
                "WHERE r.session_id = ? ORDER BY r.created_at", (session_id,)).fetchall()
        return [self._to_request(r) for r in rows]

    @staticmethod
    def _to_request(row: sqlite3.Row) -> Request:
        d = dict(row)
        raw = d.pop("result_json", None)
        d["result"] = json.loads(raw) if raw else None
        return Request(**d)

    def chat_history(self, session_id: str, before_request_id: str | None = None) -> list[dict[str, str]]:
        """Finished Q&A pairs of a session, oldest first (memory for follow-ups)."""
        turns = []
        for r in self.list_requests(session_id):
            if r.request_id == before_request_id:
                break
            if r.status == "done" and r.result and r.result.get("stop_reason") == "answered":
                turns.append({"question": r.question, "answer": r.result["answer"]})
        return turns

    # ---- progress events --------------------------------------------------- #
    def add_event(self, request_id: str, kind: str, payload: dict[str, Any] | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO request_events (request_id, ts, kind, payload) VALUES (?, ?, ?, ?)",
                      (request_id, _now(), kind, json.dumps(payload or {}, default=str)))

    def list_events(self, request_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT ts, kind, payload FROM request_events WHERE request_id = ? "
                             "ORDER BY id", (request_id,)).fetchall()
        return [{"ts": r["ts"], "kind": r["kind"], **json.loads(r["payload"])} for r in rows]

    # ---- feedback ---------------------------------------------------------- #
    def set_feedback(self, request_id: str, rating: int, comment: str | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO feedback VALUES (?, ?, ?, ?) ON CONFLICT(request_id) DO UPDATE "
                      "SET rating = excluded.rating, comment = excluded.comment",
                      (request_id, rating, comment, _now()))

    def rated_requests(self) -> list[Request]:
        """Every rated answer: raw material for new eval cases."""
        with self._conn() as c:
            rows = c.execute("SELECT r.*, f.rating FROM requests r JOIN feedback f USING (request_id) "
                             "ORDER BY r.created_at").fetchall()
        return [self._to_request(r) for r in rows]
