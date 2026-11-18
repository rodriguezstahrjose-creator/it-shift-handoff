"""python -m handoff init | run | add-demo"""
import argparse
import secrets
from werkzeug.security import generate_password_hash
from . import create_app
from .db import get_db, initialize
from .services import NoteService, new_id


def seed_demo(password=None):
    db = get_db()
    if db.execute('SELECT 1 FROM users WHERE username=?', ('technician',)).fetchone():
        return None
    password = password or secrets.token_urlsafe(15)
    actor = dict(id=new_id(), username='technician', team_id=new_id())
    db.execute('INSERT INTO users VALUES (?,?,?,?)',
                (actor['id'], actor['username'], generate_password_hash(password), actor['team_id']))
    db.commit()
    service = NoteService(actor)
    shift = service.create_shift('Fictional demo · Evening handoff')
    for text in [
        'Lab printer A still disconnects after ten minutes. Reinstalling the printer driver did not fix the disconnects. The next shift should test the printer network cable.',
        'The training portal login problem is resolved. Clearing the test browser cache restored training portal access. The technician confirmed the training portal works.',
        'The demo backup job failed at 18:00. A retry of the backup job is scheduled for 22:00. The next shift must check the backup result and record any error code.'
    ]:
        service.add_note(shift['id'], text)
    return password


def main():
    parser = argparse.ArgumentParser(description='IT Shift Handoff · local Alpha')
    parser.add_argument('command', choices=['init', 'run', 'add-demo'])
    parser.add_argument('--port', type=int, default=5055)
    args = parser.parse_args()
    app = create_app()
    if args.command in ('init', 'add-demo'):
        with app.app_context():
            initialize()
            password = seed_demo()
        if password:
            print('Fictional demo created. Username: technician')
            print('Password:', password)
            print('Save this local demo password; it is not stored in plaintext.')
        else:
            print('Database already initialized. Existing credentials and notes were kept.')
    else:
        with app.app_context():
            try:
                get_db().execute('SELECT 1 FROM users LIMIT 1')
            except Exception:
                parser.error('Initialize the database first: python -m handoff init')
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

