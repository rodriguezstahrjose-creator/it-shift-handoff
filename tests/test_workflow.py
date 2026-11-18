"""Black-box API tests against real temporary SQLite databases and TextRank."""
import copy
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from werkzeug.security import generate_password_hash
from handoff import create_app
from handoff.db import get_db, initialize
from handoff.__main__ import seed_demo
from handoff.textrank import sentences, rank


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = generate_password_hash('test-fixture-password')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': self.temp.name + '/test.sqlite'})
        self.client = self.app.test_client()
        with self.app.app_context():
            initialize()
            self.team = str(uuid4())
            self.user = str(uuid4())
            get_db().execute('INSERT INTO users VALUES (?,?,?,?)',
                             (self.user, 'reviewer', self.password_hash, self.team))
            get_db().commit()
        self.csrf = self.client.get('/api/v1/session').json['csrf_token']
        response = self.call('/session', 'POST', {'username': 'reviewer', 'password': 'test-fixture-password'})
        self.assertEqual(response.status_code, 200)
        self.csrf = response.json['csrf_token']

    def tearDown(self):
        self.temp.cleanup()

    def call(self, path, method='GET', data=None, **kwargs):
        return self.client.open('/api/v1' + path, method=method, json=data,
                                headers={'X-CSRF-Token': self.csrf}, **kwargs)

    def shift(self, text='Printer A is offline. The printer cable was replaced. Check the printer queue next shift.'):
        shift = self.call('/shifts', 'POST', {'label': 'Test shift'}).json
        if text is not None:
            response = self.call('/shifts/' + shift['id'] + '/notes', 'POST', {'text': text})
            self.assertEqual(response.status_code, 201)
        return shift['id']

    def draft(self, shift=None, mode='textrank'):
        shift = shift or self.shift()
        response = self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': mode})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def categorize(self, draft):
        for item in draft['items']:
            item['category'] = 'pending'
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT',
                             {'expected_version': draft['version'], 'items': draft['items']})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def approve(self, draft, **overrides):
        data = dict(expected_version=draft['version'], source_review_confirmed=True, completeness_confirmed=True)
        data.update(overrides)
        return self.call('/summaries/' + draft['id'] + '/approval', 'POST', data)

    def test_end_to_end_extract_review_approve_and_reload(self):
        draft = self.draft()
        for item in draft['items']:
            source = next(s for s in draft['source_sentences'] if s['id'] == item['source_sentence_id'])
            note = self.call('/notes/' + source['note_id']).json
            self.assertEqual(item['text'], note['text'][source['start']:source['end']])
        saved = self.categorize(draft)
        approved = self.approve(saved)
        self.assertEqual(approved.status_code, 201)
        result = approved.json['summary']
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['approval']['approved_by'], self.user)
        fresh = self.call('/summaries/' + result['id']).json
        self.assertEqual(fresh, result)
        self.assertEqual(self.call('/shifts/' + draft['shift_id'] + '/summaries').json['items'][0], result)

    def _add_note_from_independent_connection(self, shift_id):
        # A nested app context gives this writer its own SQLite connection.
        from handoff.services import NoteService
        with self.app.app_context():
            return NoteService({'id': self.user, 'team_id': self.team}).add_note(
                shift_id, 'Urgent: isolate the failing UPS before the next shift.')

    def _assert_generation_rejects_changed_source(self, mode):
        shift = self.shift()
        added = []

        def competing_write(source, *args):
            added.append(self._add_note_from_independent_connection(shift))
            return [source[i] for i in rank(source, args[0])] if mode == 'textrank' else sentences(source)

        target = 'handoff.services.textrank.' + ('extract' if mode == 'textrank' else 'sentences')
        with patch(target, side_effect=competing_write):
            response = self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': mode})
        self.assertEqual(response.status_code, 409, response.json)
        self.assertEqual(response.json['error']['code'], 'SOURCE_CHANGED')
        self.assertEqual(self.call('/shifts/' + shift + '/summaries').json['items'], [])
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM review_events').fetchone()[0], 0)
        # Failure must preserve the concurrent note and release the rank lock.
        fresh = self.draft(shift, mode)
        self.assertIn(added[0]['id'], fresh['source_note_ids'])
        revision = self.call('/shifts/' + shift + '/notes').json['shift_revision']
        self.assertEqual(fresh['source_revision'], revision)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM review_events').fetchone()[0], 1)

    def test_generation_rechecks_source_after_ranking(self):
        self._assert_generation_rejects_changed_source('textrank')

    def test_manual_generation_rechecks_source_before_persisting(self):
        self._assert_generation_rejects_changed_source('manual')

    def test_generation_allows_independent_shift_change(self):
        shift = self.shift()
        other = self.shift()

        def competing_write(source, count, timeout):
            self._add_note_from_independent_connection(other)
            return [source[i] for i in rank(source, count)]

        with patch('handoff.services.textrank.extract', side_effect=competing_write):
            draft = self.draft(shift)
        self.assertEqual(len(draft['source_note_ids']), 1)
        self.assertEqual(self.approve(self.categorize(draft)).status_code, 201)

    def test_approval_requires_categories_and_confirmations(self):
        draft = self.draft()
        self.assertEqual(self.approve(draft).json['error']['code'], 'REVIEW_INCOMPLETE')
        draft = self.categorize(draft)
        self.assertEqual(self.approve(draft, source_review_confirmed=False).status_code, 422)
        self.assertEqual(self.approve(draft, completeness_confirmed=1).status_code, 422)

    def test_empty_manual_draft_cannot_be_approved(self):
        draft = self.draft(mode='manual')
        self.assertEqual(draft['items'], [])
        self.assertEqual(self.approve(draft).status_code, 422)

    def test_manual_review_and_technician_addition(self):
        draft = self.draft(mode='manual')
        item = dict(item_id=str(uuid4()), origin='technician', text='Check the test queue.',
                    category='pending', source_sentence_id=None)
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT',
                             dict(expected_version=1, items=[item]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.approve(response.json).status_code, 201)

    def test_rewrite_preserves_original_extraction_in_audit(self):
        draft = self.draft()
        original = copy.deepcopy(draft['items'])
        draft['items'][0] = dict(item_id=str(uuid4()), origin='technician', text='Technician clarification.',
                                category='pending', source_sentence_id=None)
        saved = self.categorize(draft)
        with self.app.app_context():
            events = get_db().execute('SELECT kind,items FROM review_events WHERE summary_id=? ORDER BY id',
                                      (saved['id'],)).fetchall()
            import json
            self.assertEqual(json.loads(events[0]['items']), original)
            self.assertEqual(events[-1]['kind'], 'review_saved')

    def test_extraction_references_cannot_transfer_between_drafts(self):
        """Regression for the recovery failure described in the Unit 4 reflection."""
        first = self.draft()
        manual = self.draft(first['shift_id'], mode='manual')
        response = self.call('/summaries/' + manual['id'] + '/review', 'PUT',
                             dict(expected_version=1, items=first['items']))
        self.assertEqual(response.status_code, 422)
        fresh = self.draft(first['shift_id'])
        response = self.call('/summaries/' + fresh['id'] + '/review', 'PUT',
                             dict(expected_version=1, items=first['items']))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.approve(self.categorize(fresh)).status_code, 201)

    def test_critical_action_recovery_for_discussion_stress_cases(self):
        """A global quality score must not replace source access and manual recovery."""
        import json
        from pathlib import Path
        cases = json.loads((Path(__file__).resolve().parent.parent / 'data/review-stress-cases.json').read_text())
        for case in cases:
            with self.subTest(case=case['id']):
                shift = self.shift(None)
                for text in case['notes']:
                    self.call('/shifts/' + shift + '/notes', 'POST', {'text': text})
                draft = self.draft(shift)
                originals = self.call('/shifts/' + shift + '/notes').json['items']
                self.assertTrue(any(case['critical_action'] in n['text'] for n in originals))
                draft['items'].append(dict(item_id=str(uuid4()), origin='technician',
                    text=case['critical_action'], category='pending', source_sentence_id=None))
                approved = self.approve(self.categorize(draft)).json['summary']
                self.assertTrue(any(i['origin'] == 'technician' and i['text'] == case['critical_action']
                                    for i in approved['items']))

    def test_tampering_with_extraction_is_rejected(self):
        for key, value in [('text', 'invented sentence'), ('source_sentence_id', str(uuid4())),
                           ('item_id', str(uuid4())), ('origin', 'technician')]:
            with self.subTest(key=key):
                draft = self.draft()
                draft['items'][0][key] = value
                response = self.call('/summaries/' + draft['id'] + '/review', 'PUT',
                                     dict(expected_version=1, items=draft['items']))
                self.assertEqual(response.status_code, 422)

    def test_approved_handoff_is_immutable_and_approval_retry_is_idempotent(self):
        draft = self.categorize(self.draft())
        first = self.approve(draft).json
        self.assertEqual(self.approve(draft).json, first)
        self.assertEqual(self.approve(draft, expected_version=999).status_code, 409)
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT',
                             dict(expected_version=first['summary']['version'], items=[]))
        self.assertEqual(response.status_code, 409)

    def test_new_notes_make_draft_stale(self):
        draft = self.categorize(self.draft())
        self.call('/shifts/' + draft['shift_id'] + '/notes', 'POST', {'text': 'New unresolved problem.'})
        self.assertEqual(self.approve(draft).json['error']['code'], 'SOURCE_CHANGED')
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT',
                             dict(expected_version=draft['version'], items=draft['items']))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.draft(draft['shift_id'])['source_revision'], draft['source_revision'] + 1)

    def test_stale_review_version_and_noop_save(self):
        draft = self.draft()
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT', dict(expected_version=1, items=draft['items']))
        self.assertEqual(response.json['version'], 1)
        self.categorize(draft)
        response = self.call('/summaries/' + draft['id'] + '/review', 'PUT', dict(expected_version=1, items=[]))
        self.assertEqual(response.json['error']['code'], 'VERSION_CONFLICT')

    def test_unicode_offsets_are_exact(self):
        draft = self.draft(self.shift('  Café router 🔌 is offline.\n Check café router power.\nPower was restored!  '))
        note = self.call('/notes/' + draft['source_note_ids'][0]).json
        for source in draft['source_sentences']:
            self.assertEqual(source['text'], note['text'][source['start']:source['end']])
        self.assertEqual(len(draft['source_sentences']), 3)

    def test_source_text_is_preserved_as_plain_text(self):
        text = '<script>alert("x")</script> Router is offline.'
        draft = self.draft(self.shift(text))
        self.assertEqual(self.call('/notes/' + draft['source_note_ids'][0]).json['text'], text)
        page = self.client.get('/')
        self.assertNotIn(text.encode(), page.data)
        self.assertIn("script-src 'self'", page.headers['Content-Security-Policy'])

    def test_note_validation_and_injection_string(self):
        shift = self.shift(None)
        for text in ['', '   ', 'x' * 5001, None, 44]:
            self.assertEqual(self.call('/shifts/' + shift + '/notes', 'POST', {'text': text}).status_code, 422)
        text = "'); DROP TABLE notes; --"
        self.assertEqual(self.call('/shifts/' + shift + '/notes', 'POST', {'text': text}).status_code, 201)
        self.assertEqual(self.call('/shifts/' + shift + '/notes').json['items'][0]['text'], text)

    def test_empty_and_oversize_shift_bounds(self):
        empty = self.shift(None)
        self.assertEqual(self.call('/shifts/' + empty + '/summaries', 'POST', {'mode': 'textrank'}).json['error']['code'], 'NO_NOTES')
        shift = self.shift('x' * 5000)
        for text in ['y' * 5000, 'z']:
            self.call('/shifts/' + shift + '/notes', 'POST', {'text': text})
        for mode in ['textrank', 'manual']:
            self.assertEqual(self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': mode}).json['error']['code'], 'INPUT_LIMIT_EXCEEDED')

    def test_sentence_bounds_and_long_sentence_manual_fallback(self):
        shift = self.shift('X. ' * 201)
        self.assertEqual(self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': 'manual'}).status_code, 422)
        shift = self.shift('x' * 2001)
        self.assertEqual(self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': 'textrank'}).json['error']['code'], 'SENTENCE_TOO_LONG')
        self.assertEqual(self.draft(shift, mode='manual')['items'], [])

    def test_pagination_does_not_limit_summary_snapshot(self):
        shift = self.shift(None)
        for i in range(27):
            self.call('/shifts/' + shift + '/notes', 'POST', {'text': f'Router {i} is offline.'})
        first = self.call('/shifts/' + shift + '/notes?limit=25').json
        rest = self.call('/shifts/' + shift + '/notes?after_seq=' + str(first['next_after_seq'])).json
        self.assertEqual((len(first['items']), len(rest['items'])), (25, 2))
        self.assertEqual(len(self.draft(shift)['source_note_ids']), 27)

    def test_invalid_payloads_are_consistent_errors(self):
        shift = self.shift()
        cases = [('/shifts', {'label': 'ok', 'extra': 1}),
                 ('/shifts', {'label': []}),
                 ('/shifts/' + shift + '/summaries', {'mode': 'manual', 'max_sentences': 2}),
                 ('/shifts/' + shift + '/summaries', {'mode': 'unknown'}),
                 ('/shifts/' + shift + '/summaries', {'mode': 'textrank', 'max_sentences': True}),
                 ('/shifts/' + shift + '/summaries', {'mode': 'textrank', 'max_sentences': None})]
        for path, payload in cases:
            self.assertEqual(self.call(path, 'POST', payload).status_code, 422)
        for query in ['limit=0', 'limit=101', 'limit=x', 'limit=2&limit=3', 'extra=x', 'after_seq=-1']:
            self.assertEqual(self.call('/shifts?' + query).status_code, 422)
        self.assertEqual(self.call('/notes/not-a-uuid').status_code, 422)

    def test_malformed_media_and_oversize_request(self):
        headers = {'X-CSRF-Token': self.csrf}
        self.assertEqual(self.client.post('/api/v1/shifts', data='bad', headers=headers).status_code, 415)
        self.assertEqual(self.client.post('/api/v1/shifts', data='{', content_type='application/json', headers=headers).status_code, 400)
        self.assertEqual(self.call('/shifts', 'POST', {'label': 'x' * 70000}).status_code, 413)

    def test_requires_authentication_and_csrf(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/api/v1/shifts').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/shifts', json={'label': 'blocked'}).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/shifts', json={'label': 'blocked'}, headers={'X-CSRF-Token': 'é'}).status_code, 403)

    def test_other_team_cannot_access_resources(self):
        draft = self.draft()
        with self.app.app_context():
            get_db().execute('UPDATE users SET team_id=? WHERE id=?', (str(uuid4()), self.user))
            get_db().commit()
        for path, method, data in [('/notes/' + draft['source_note_ids'][0], 'GET', None),
            ('/shifts/' + draft['shift_id'] + '/notes', 'GET', None),
            ('/shifts/' + draft['shift_id'] + '/summaries', 'POST', {'mode': 'manual'}),
            ('/summaries/' + draft['id'], 'GET', None),
            ('/summaries/' + draft['id'] + '/review', 'PUT', {'expected_version': 1, 'items': []}),
            ('/summaries/' + draft['id'] + '/approval', 'POST', {'expected_version': 1, 'source_review_confirmed': True, 'completeness_confirmed': True})]:
            self.assertEqual(self.call(path, method, data).status_code, 404, path)

    def test_login_rotates_session_and_logout_invalidates_it(self):
        old = self.csrf
        response = self.call('/session', 'POST', {'username': 'reviewer', 'password': 'test-fixture-password'})
        self.csrf = response.json['csrf_token']
        self.assertNotEqual(old, self.csrf)
        cookie = response.headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Lax', cookie)
        self.assertEqual(self.call('/session', 'DELETE').status_code, 204)
        self.assertEqual(self.call('/shifts').status_code, 401)

    def test_session_expiry(self):
        with self.app.app_context():
            get_db().execute('UPDATE sessions SET touched=?', (time.time() - 1801,))
            get_db().commit()
        self.assertEqual(self.call('/shifts').status_code, 401)
        self.assertFalse(self.call('/session').json['authenticated'])

    def test_login_throttling(self):
        for _ in range(5):
            self.assertEqual(self.call('/session', 'POST', {'username': 'absent', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.call('/session', 'POST', {'username': 'absent', 'password': 'wrong'}).status_code, 429)

    def test_timeout_and_failure_leave_notes_and_manual_drafting_available(self):
        shift = self.shift()
        with patch('handoff.textrank.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', .01)):
            response = self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': 'textrank'})
            self.assertEqual(response.json['error']['code'], 'AI_TIMEOUT')
        with patch('handoff.textrank.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'worker')):
            self.assertEqual(self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': 'textrank'}).status_code, 503)
        self.assertEqual(len(self.call('/shifts/' + shift + '/notes').json['items']), 1)
        self.assertEqual(self.draft(shift, 'manual')['status'], 'draft')

    def test_busy_ranker_returns_actionable_error(self):
        shift = self.shift()
        lock = self.app.extensions['rank_lock']
        lock.acquire()
        try:
            self.assertEqual(self.call('/shifts/' + shift + '/summaries', 'POST', {'mode': 'textrank'}).status_code, 503)
        finally:
            lock.release()

    def test_storage_failure_rolls_back_note_and_revision(self):
        shift = self.shift()
        with self.app.app_context():
            get_db().execute("CREATE TRIGGER reject_notes BEFORE INSERT ON notes BEGIN SELECT RAISE(ABORT,'simulated'); END")
        self.assertEqual(self.call('/shifts/' + shift + '/notes', 'POST', {'text': 'Must not persist.'}).status_code, 503)
        notes = self.call('/shifts/' + shift + '/notes').json
        self.assertEqual(len(notes['items']), 1)
        self.assertEqual(notes['shift_revision'], 2)

    def test_incomplete_and_duplicate_review_items_rejected(self):
        draft = self.draft()
        for items in [[{}], draft['items'] + [draft['items'][0]], 'not a list', [dict(item_id='no')]]:
            response = self.call('/summaries/' + draft['id'] + '/review', 'PUT', {'expected_version': 1, 'items': items})
            self.assertIn(response.status_code, (400, 422))

    def test_seed_does_not_overwrite_existing_data(self):
        with self.app.app_context():
            self.assertTrue(seed_demo())
            self.assertIsNone(seed_demo())


class TextRankTests(unittest.TestCase):
    def test_related_sentences_rank_above_isolated_sentence(self):
        source = [{'text': x} for x in ['Printer queue printer error.', 'Printer queue needs attention.', 'Banana orchard sunshine.']]
        self.assertEqual(rank(source, 2), [0, 1])

    def test_disconnected_sentences_have_deterministic_ties(self):
        self.assertEqual(rank([{'text': 'alpha'}, {'text': 'beta'}, {'text': 'gamma'}], 2), [0, 1])
        self.assertEqual(rank([], 3), [])

    def test_source_boundaries_and_whitespace(self):
        text = '  One sentence!\nTwo words\n   '
        result = sentences([{'id': 'test', 'text': text}])
        self.assertEqual([s['text'] for s in result], ['One sentence!', 'Two words'])
        for s in result:
            self.assertEqual(text[s['start']:s['end']], s['text'])


if __name__ == '__main__':
    unittest.main()
