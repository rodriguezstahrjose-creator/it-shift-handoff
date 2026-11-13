"""Thin API layer; application rules live in services."""
from flask import Blueprint, g, jsonify, render_template, request
from . import auth
from .errors import DomainError
from .repository import Repository
from .services import HandoffService, NoteService, SummaryService
from .validation import body, page, uuid

web = Blueprint('web', __name__)
api = Blueprint('api', __name__, url_prefix='/api/v1')


@web.get('/')
def index():
    return render_template('index.html')


@api.route('/session', methods=['GET', 'POST', 'DELETE'])
def session():
    if request.method == 'GET':
        return jsonify(auth.status())
    if request.method == 'POST':
        data = body(('username', 'password'))
        return jsonify(auth.sign_in(data['username'], data['password']))
    auth.check_csrf()
    auth.sign_out()
    return '', 204


@api.route('/shifts', methods=['GET', 'POST'])
@auth.protected
def shifts():
    service = NoteService(g.actor)
    if request.method == 'POST':
        return jsonify(service.create_shift(body(('label',))['label'])), 201
    return jsonify(service.list_shifts(*page()))


@api.route('/shifts/<shift_id>/notes', methods=['GET', 'POST'])
@auth.protected
def notes(shift_id):
    uuid(shift_id)
    service = NoteService(g.actor)
    if request.method == 'POST':
        return jsonify(service.add_note(shift_id, body(('text',))['text'])), 201
    return jsonify(service.list_notes(shift_id, *page()))


@api.get('/notes/<note_id>')
@auth.protected
def note(note_id):
    return jsonify(Repository(g.actor).note(uuid(note_id)))


@api.route('/shifts/<shift_id>/summaries', methods=['GET', 'POST'])
@auth.protected
def generate(shift_id):
    uuid(shift_id)
    if request.method == 'GET':
        after, limit = page()
        repo = Repository(g.actor)
        repo.shift(shift_id)
        # Additive Alpha endpoint: reload persisted drafts/approved handoffs.
        import json
        rows = repo.db.execute('SELECT rowid,body FROM summaries WHERE shift_id=? AND rowid>? '
                                'ORDER BY rowid LIMIT ?', (shift_id, after, limit)).fetchall()
        return jsonify(items=[json.loads(r['body']) for r in rows],
                       next_after_seq=rows[-1]['rowid'] if rows else after)
    data = body(('mode',), ('max_sentences',))
    if 'max_sentences' in data and data['max_sentences'] is None:
        raise DomainError('VALIDATION_ERROR', 'max_sentences cannot be null.')
    return jsonify(SummaryService(g.actor).generate(shift_id, data['mode'], data.get('max_sentences'))), 201


@api.get('/summaries/<summary_id>')
@auth.protected
def summary(summary_id):
    return jsonify(Repository(g.actor).summary(uuid(summary_id)))


@api.put('/summaries/<summary_id>/review')
@auth.protected
def review(summary_id):
    data = body(('expected_version', 'items'))
    return jsonify(HandoffService(g.actor).save_review(uuid(summary_id), data['expected_version'], data['items']))


@api.post('/summaries/<summary_id>/approval')
@auth.protected
def approval(summary_id):
    data = body(('expected_version', 'source_review_confirmed', 'completeness_confirmed'))
    return jsonify(HandoffService(g.actor).approve(uuid(summary_id), data['expected_version'],
                   data['source_review_confirmed'], data['completeness_confirmed'])), 201

