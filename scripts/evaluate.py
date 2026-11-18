"""Reproducible synthetic quality + API latency measurement; no production claims."""
import argparse
import json
import platform
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from handoff import create_app
from handoff.db import get_db, initialize
from handoff.services import NoteService, new_id
from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/evaluation-results.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    scenarios = json.loads((root / 'data/scenarios.json').read_text())
    report = {'measured_at_utc': datetime.now(timezone.utc).isoformat(),
              'machine': platform.machine(), 'platform': platform.platform(),
              'python': platform.python_version(), 'measure': 'Full Flask test-client summary POST, including DB and worker startup; excludes network/browser.',
              'quality_method': 'Exact source-sentence recall against synthetic reference indices fixed before evaluation. Each scenario has three required sentences. Not a real-user study.',
              'scenarios': [], 'boundary_latency_seconds': []}
    with tempfile.TemporaryDirectory() as directory:
        app = create_app({'TESTING': True, 'DATABASE': directory + '/evaluation.sqlite'})
        actor = dict(id=new_id(), username='evaluation', team_id=new_id())
        with app.app_context():
            initialize()
            get_db().execute('INSERT INTO users VALUES (?,?,?,?)',
                             (actor['id'], actor['username'], generate_password_hash('evaluation-fixture'), actor['team_id']))
            get_db().commit()
        client = app.test_client()
        csrf = client.get('/api/v1/session').json['csrf_token']
        csrf = client.post('/api/v1/session', json=dict(username='evaluation', password='evaluation-fixture'),
                           headers={'X-CSRF-Token': csrf}).json['csrf_token']
        for scenario in scenarios:
            with app.app_context():
                service = NoteService(actor)
                shift = service.create_shift(scenario['id'])
                for text in scenario['notes']:
                    service.add_note(shift['id'], text)
            for count in [3, 5]:
                started = time.perf_counter()
                response = client.post('/api/v1/shifts/' + shift['id'] + '/summaries',
                                       json=dict(mode='textrank', max_sentences=count),
                                       headers={'X-CSRF-Token': csrf})
                elapsed = time.perf_counter() - started
                if response.status_code != 201:
                    raise RuntimeError(response.json)
                draft = response.json
                chosen_ids = {i['source_sentence_id'] for i in draft['items']}
                chosen_indices = [i for i, s in enumerate(draft['source_sentences']) if s['id'] in chosen_ids]
                required = scenario['required_sentence_indices']
                captured = [i for i in required if i in chosen_indices]
                report['scenarios'].append(dict(id=scenario['id'], split=scenario['split'],
                    requested_sentences=count, source_sentences=len(draft['source_sentences']),
                    selected_indices=chosen_indices, captured=len(captured), required=len(required),
                    omitted_indices=[i for i in required if i not in captured], latency_seconds=elapsed))
        # 200 sentences, exactly 10,000 code points across two maximum-size notes.
        units = []
        for i in range(100):
            prefix = f'Router {i:03d} check next shift '
            units.append(prefix + 'x' * (48 - len(prefix)) + '.')
        units[0] = units[0][:-1] + ' .'
        text = '\n'.join(units)
        assert len(text) == 5000
        with app.app_context():
            service = NoteService(actor)
            shift = service.create_shift('Boundary: 10000 characters, 200 sentences')
            service.add_note(shift['id'], text)
            service.add_note(shift['id'], text)
        for mode in ['manual', 'textrank']:
            for _ in range(3):
                started = time.perf_counter()
                payload = dict(mode=mode)
                if mode == 'textrank':
                    payload['max_sentences'] = 5
                response = client.post('/api/v1/shifts/' + shift['id'] + '/summaries',
                                       json=payload, headers={'X-CSRF-Token': csrf})
                report['boundary_latency_seconds'].append(dict(mode=mode, characters=10000, sentences=200,
                    status=response.status_code, seconds=time.perf_counter()-started))
                if response.status_code != 201:
                    raise RuntimeError(response.json)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    for count in [3, 5]:
        rows = [r for r in report['scenarios'] if r['split'] == 'evaluation' and r['requested_sentences'] == count]
        captured, required = sum(r['captured'] for r in rows), sum(r['required'] for r in rows)
        print(f'Evaluation, {count} sentences: {captured}/{required} required items ({captured/required:.1%}); max API time {max(r["latency_seconds"] for r in rows):.3f}s')
    print('Boundary measurements:', report['boundary_latency_seconds'])


if __name__ == '__main__':
    main()
