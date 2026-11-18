"""Workflow rules independent of HTTP and browser behavior."""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from flask import current_app
from .db import get_db
from .errors import DomainError
from .repository import Repository
from . import textrank
from .validation import fields, integer, string, uuid


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def new_id():
    return str(uuid4())


@contextmanager
def transaction():
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


class NoteService:
    def __init__(self, actor):
        self.repo = Repository(actor)

    def create_shift(self, label):
        label = string(label, 'label', maximum=80)
        actor = self.repo.actor
        with transaction() as db:
            seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM shifts WHERE team_id=?',
                             (actor['team_id'],)).fetchone()[0]
            item = dict(id=new_id(), team_id=actor['team_id'], label=label, seq=seq,
                        revision=1, created_at=now())
            db.execute('INSERT INTO shifts VALUES (:id,:team_id,:label,:seq,:revision,:created_at)', item)
        return item

    def add_note(self, shift_id, text):
        text = string(text, 'text', maximum=5000)
        with transaction() as db:
            self.repo.shift(shift_id)
            seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM notes WHERE shift_id=?',
                             (shift_id,)).fetchone()[0]
            note = dict(id=new_id(), shift_id=shift_id, author_id=self.repo.actor['id'],
                        seq=seq, text=text, created_at=now())
            db.execute('INSERT INTO notes VALUES (:id,:shift_id,:author_id,:seq,:text,:created_at)', note)
            db.execute('UPDATE shifts SET revision=revision+1 WHERE id=?', (shift_id,))
        return note

    def list_shifts(self, after, limit):
        rows = [dict(r) for r in self.repo.db.execute(
            'SELECT * FROM shifts WHERE team_id=? AND seq>? ORDER BY seq LIMIT ?',
            (self.repo.actor['team_id'], after, limit))]
        return dict(items=rows, next_after_seq=rows[-1]['seq'] if rows else after)

    def list_notes(self, shift_id, after, limit):
        # One read transaction keeps revision and returned notes consistent.
        with transaction() as db:
            shift = self.repo.shift(shift_id)
            rows = [dict(r) for r in db.execute(
                'SELECT * FROM notes WHERE shift_id=? AND seq>? ORDER BY seq LIMIT ?',
                (shift_id, after, limit))]
        return dict(items=rows, next_after_seq=rows[-1]['seq'] if rows else after,
                    shift_revision=shift['revision'])


class SummaryService:
    def __init__(self, actor):
        self.repo = Repository(actor)

    def generate(self, shift_id, mode, max_sentences=None):
        if mode not in ('textrank', 'manual'):
            raise DomainError('VALIDATION_ERROR', 'Choose textrank or manual mode.')
        if mode == 'manual' and max_sentences is not None:
            raise DomainError('VALIDATION_ERROR', 'Manual mode does not accept max_sentences.')
        count = integer(max_sentences if max_sentences is not None else 3, 'max_sentences', 1, 10)
        with transaction():
            shift = self.repo.shift(shift_id)
            notes = self.repo.notes(shift_id)
        if not notes:
            raise DomainError('NO_NOTES', 'Add a note before creating a draft.')
        if sum(len(n['text']) for n in notes) > 10000:
            raise DomainError('INPUT_LIMIT_EXCEEDED', 'This shift exceeds the 10,000 character summary limit.')
        source = textrank.sentences(notes)
        if len(source) > 200:
            raise DomainError('INPUT_LIMIT_EXCEEDED', 'This shift exceeds the 200 sentence summary limit.')
        if mode == 'textrank':
            guard = current_app.extensions['rank_lock']
            if not guard.acquire(blocking=False):
                raise DomainError('AI_UNAVAILABLE', 'Another summary is running. Try again shortly.', 503)
            try:
                chosen = textrank.extract(source, count, current_app.config['RANK_TIMEOUT'])
            finally:
                guard.release()
            if any(len(s['text']) > 2000 for s in chosen):
                raise DomainError('SENTENCE_TOO_LONG', 'A selected sentence is too long. Use a manual draft.')
        else:
            chosen = []
        summary = dict(id=new_id(), shift_id=shift_id, created_by=self.repo.actor['id'],
                       mode=mode, status='draft', version=1, source_revision=shift['revision'],
                       source_note_ids=[n['id'] for n in notes], source_sentences=source,
                       items=[dict(item_id=new_id(), origin='extracted', text=s['text'],
                                   category='unassigned', source_sentence_id=s['id']) for s in chosen],
                       created_at=now(), algorithm_version=textrank.ALGORITHM_VERSION if chosen else None,
                       approval=None)
        with transaction() as db:
            # Ranking runs without a database write lock. Recheck under the same
            # write transaction as the insert so a new note cannot slip between
            # validation and persistence (manual drafts need this check too).
            if self.repo.shift(shift_id)['revision'] != summary['source_revision']:
                raise DomainError('SOURCE_CHANGED',
                                  'New notes were added while preparing the draft. Generate a fresh draft.', 409)
            db.execute('INSERT INTO summaries VALUES (?,?,?,?)',
                        (summary['id'], shift_id, self.repo.actor['id'], json.dumps(summary)))
            self.repo.event(summary, 'generated', now())
        return summary


class HandoffService:
    CATEGORIES = ('unresolved', 'completed', 'pending', 'unassigned')

    def __init__(self, actor):
        self.repo = Repository(actor)

    def save_review(self, summary_id, expected_version, items):
        integer(expected_version, 'expected_version')
        if not isinstance(items, list) or len(items) > 30:
            raise DomainError('VALIDATION_ERROR', 'A review can contain up to 30 items.')
        with transaction():
            summary = self.repo.summary(summary_id)
            if summary['status'] != 'draft':
                raise DomainError('ALREADY_APPROVED', 'Approved handoffs cannot be edited.', 409)
            if expected_version != summary['version']:
                raise DomainError('VERSION_CONFLICT', 'This draft changed. Reload it before saving.', 409)
            self._check_source(summary)
            original = self.repo.db.execute(
                "SELECT items FROM review_events WHERE summary_id=? AND kind='generated' ORDER BY id LIMIT 1",
                (summary_id,)).fetchone()
            extraction = {i['item_id']: i for i in json.loads(original['items'])}
            seen = set()
            checked = []
            for item in items:
                fields(item, ('item_id', 'origin', 'text', 'category', 'source_sentence_id'))
                item_id = uuid(item['item_id'])
                if item_id in seen:
                    raise DomainError('VALIDATION_ERROR', 'Item IDs must be unique.')
                seen.add(item_id)
                text = string(item['text'], 'text', maximum=2000, trim=False)
                if not text.strip() or item['category'] not in self.CATEGORIES:
                    raise DomainError('VALIDATION_ERROR', 'Each item needs text and a valid category.')
                if item['origin'] == 'extracted':
                    match = extraction.get(item_id)
                    if not match or any(item[k] != match[k] for k in ('text', 'source_sentence_id')):
                        raise DomainError('VALIDATION_ERROR', 'Extracted text and source references must stay unchanged.')
                elif item['origin'] == 'technician':
                    if item['source_sentence_id'] is not None or item_id in extraction:
                        raise DomainError('VALIDATION_ERROR', 'Technician items must use a new ID and no source reference.')
                else:
                    raise DomainError('VALIDATION_ERROR', 'Invalid item origin.')
                checked.append(dict(item))
            if checked != summary['items']:
                summary['items'] = checked
                summary['version'] += 1
                self.repo.save_summary(summary)
                self.repo.event(summary, 'review_saved', now())
        return summary

    def _check_source(self, summary):
        if self.repo.shift(summary['shift_id'])['revision'] != summary['source_revision']:
            raise DomainError('SOURCE_CHANGED', 'New notes were added. Generate a fresh draft before approval.', 409)

    def approve(self, summary_id, expected_version, source_confirmed, complete_confirmed):
        integer(expected_version, 'expected_version')
        if source_confirmed is not True or complete_confirmed is not True:
            raise DomainError('REVIEW_INCOMPLETE', 'Confirm source review and completeness before approval.')
        with transaction():
            summary = self.repo.summary(summary_id)
            if summary['status'] == 'approved':
                if summary['version'] - 1 == expected_version:
                    return dict(approval=summary['approval'], summary=summary)
                raise DomainError('ALREADY_APPROVED', 'This handoff is already approved.', 409)
            if expected_version != summary['version']:
                raise DomainError('VERSION_CONFLICT', 'This draft changed. Reload it before approval.', 409)
            self._check_source(summary)
            if not summary['items'] or any(i['category'] == 'unassigned' for i in summary['items']):
                raise DomainError('REVIEW_INCOMPLETE', 'Assign a category to every item before approval.')
            summary['version'] += 1
            summary['status'] = 'approved'
            summary['approval'] = dict(id=new_id(), summary_id=summary_id,
                                       approved_by=self.repo.actor['id'],
                                       approved_version=summary['version'], approved_at=now(),
                                       source_revision=summary['source_revision'])
            self.repo.save_summary(summary)
            self.repo.event(summary, 'approved', now())
        return dict(approval=summary['approval'], summary=summary)

