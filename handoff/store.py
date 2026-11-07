"""SQLite core. Actor IDs are trusted caller inputs until authentication is added.

Never expose this component directly to untrusted callers.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from .ranking import extract


class RuleError(ValueError):
    pass


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS shifts (
                id TEXT PRIMARY KEY, team_id TEXT NOT NULL, label TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS notes (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                shift_id TEXT NOT NULL REFERENCES shifts(id), text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY, shift_id TEXT NOT NULL REFERENCES shifts(id),
                payload TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def shift(self, team_id, shift_id):
        row = self.db.execute("SELECT * FROM shifts WHERE id=? AND team_id=?",
                              (shift_id, team_id)).fetchone()
        if row is None:
            raise RuleError("NOT_FOUND")
        return dict(row)

    def create_shift(self, team_id, label):
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
            raise RuleError("VALIDATION_ERROR")
        shift_id = uid()
        self.db.execute("INSERT INTO shifts(id,team_id,label) VALUES (?,?,?)",
                        (shift_id, team_id, label.strip()))
        return self.shift(team_id, shift_id)

    def add_note(self, team_id, shift_id, text):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 5000:
            raise RuleError("VALIDATION_ERROR")
        with self.transaction():
            self.shift(team_id, shift_id)
            note_id = uid()
            self.db.execute("INSERT INTO notes(id,shift_id,text) VALUES (?,?,?)",
                            (note_id, shift_id, text.strip()))
            self.db.execute("UPDATE shifts SET revision=revision+1 WHERE id=?", (shift_id,))
        return note_id

    def notes(self, team_id, shift_id):
        self.shift(team_id, shift_id)
        return [dict(n) for n in self.db.execute(
            "SELECT id,shift_id,text FROM notes WHERE shift_id=? ORDER BY seq", (shift_id,))]

    def generate(self, team_id, shift_id, mode="textrank", max_sentences=None):
        if mode not in ("textrank", "manual") or (mode == "manual" and max_sentences is not None):
            raise RuleError("VALIDATION_ERROR")
        with self.transaction():
            shift = self.shift(team_id, shift_id)
            notes = self.notes(team_id, shift_id)
            if not notes:
                raise RuleError("NO_NOTES")
            # Manual drafts must obey the same snapshot size limits.
            from .ranking import sentences
            if sum(len(n["text"]) for n in notes) > 10_000 or len(sentences(notes)) > 200:
                raise RuleError("INPUT_LIMIT_EXCEEDED")
            try:
                source = extract(notes, 3 if max_sentences is None else max_sentences) if mode == "textrank" else []
            except ValueError as error:
                raise RuleError(str(error)) from error
            items = [{"item_id": uid(), "origin": "extracted", "text": s["text"],
                      "source_sentence_id": s["id"], "category": "unassigned"} for s in source]
            draft = {"id": uid(), "shift_id": shift_id, "mode": mode,
                     "source_revision": shift["revision"], "source_note_ids": [n["id"] for n in notes],
                     "source_sentences": source, "original_items": items,
                     "items": items, "status": "draft", "version": 1,
                     "approval": None, "created_at": now()}
            self.db.execute("INSERT INTO summaries VALUES (?,?,?)",
                            (draft["id"], shift_id, json.dumps(draft)))
        return draft

    def summary(self, team_id, summary_id):
        row = self.db.execute("SELECT * FROM summaries WHERE id=?", (summary_id,)).fetchone()
        if row is None:
            raise RuleError("NOT_FOUND")
        self.shift(team_id, row["shift_id"])
        return json.loads(row["payload"])

    def persist(self, draft):
        self.db.execute("UPDATE summaries SET payload=? WHERE id=?",
                        (json.dumps(draft), draft["id"]))
