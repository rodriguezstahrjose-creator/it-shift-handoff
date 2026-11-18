"""SQLite storage; all user content is supplied as bound parameters."""
import sqlite3
from flask import current_app, g

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 team_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id),
 csrf TEXT NOT NULL, touched REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (
 username TEXT NOT NULL, address TEXT NOT NULL, attempted REAL NOT NULL);
CREATE TABLE IF NOT EXISTS shifts (
 id TEXT PRIMARY KEY, team_id TEXT NOT NULL, label TEXT NOT NULL,
 seq INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 UNIQUE(team_id,seq));
CREATE TABLE IF NOT EXISTS notes (
 id TEXT PRIMARY KEY, shift_id TEXT NOT NULL REFERENCES shifts(id),
 author_id TEXT NOT NULL REFERENCES users(id), seq INTEGER NOT NULL,
 text TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(shift_id,seq));
CREATE TABLE IF NOT EXISTS summaries (
 id TEXT PRIMARY KEY, shift_id TEXT NOT NULL REFERENCES shifts(id),
 created_by TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS review_events (
 id INTEGER PRIMARY KEY, summary_id TEXT NOT NULL REFERENCES summaries(id),
 actor_id TEXT NOT NULL REFERENCES users(id), version INTEGER NOT NULL,
 kind TEXT NOT NULL, items TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=3)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def initialize():
    get_db().executescript(SCHEMA)

