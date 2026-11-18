"""Ownership-scoped persistence; service transactions use BEGIN IMMEDIATE."""
import json
from .db import get_db
from .errors import DomainError


class Repository:
    def __init__(self, actor):
        self.actor = actor
        self.db = get_db()

    def shift(self, shift_id):
        row = self.db.execute('SELECT * FROM shifts WHERE id=? AND team_id=?',
                              (shift_id, self.actor['team_id'])).fetchone()
        if row is None:
            raise DomainError('NOT_FOUND', 'This resource was not found.', 404)
        return dict(row)

    def note(self, note_id):
        row = self.db.execute('SELECT n.* FROM notes n JOIN shifts s ON s.id=n.shift_id '
                              'WHERE n.id=? AND s.team_id=?',
                              (note_id, self.actor['team_id'])).fetchone()
        if row is None:
            raise DomainError('NOT_FOUND', 'This resource was not found.', 404)
        return dict(row)

    def notes(self, shift_id):
        self.shift(shift_id)
        return [dict(row) for row in self.db.execute(
            'SELECT * FROM notes WHERE shift_id=? ORDER BY seq', (shift_id,))]

    def summary(self, summary_id):
        row = self.db.execute('SELECT m.body FROM summaries m JOIN shifts s ON s.id=m.shift_id '
                              'WHERE m.id=? AND s.team_id=?',
                              (summary_id, self.actor['team_id'])).fetchone()
        if row is None:
            raise DomainError('NOT_FOUND', 'This resource was not found.', 404)
        return json.loads(row['body'])

    def save_summary(self, summary):
        self.db.execute('UPDATE summaries SET body=? WHERE id=?',
                        (json.dumps(summary), summary['id']))

    def event(self, summary, kind, timestamp):
        self.db.execute('INSERT INTO review_events '
                        '(summary_id,actor_id,version,kind,items,created_at) VALUES (?,?,?,?,?,?)',
                        (summary['id'], self.actor['id'], summary['version'], kind,
                         json.dumps(summary['items']), timestamp))

