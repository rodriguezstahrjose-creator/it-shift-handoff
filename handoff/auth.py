"""Opaque server-side sessions, CSRF checks, and persistent sign-in throttling."""
import hashlib
import re
import secrets
import time
from functools import wraps
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .errors import DomainError
from .validation import string

COOKIE = 'handoff_session'
_DUMMY_HASH = generate_password_hash('unavailable-account-timing-placeholder')


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(user_id=None):
    db = get_db()
    token, csrf = secrets.token_hex(32), secrets.token_hex(32)
    db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(token), user_id, csrf, time.time()))
    db.commit()
    g.session_hash, g.csrf = digest(token), csrf
    g.set_session_token = token
    g.actor = None
    if user_id:
        g.actor = dict(db.execute('SELECT id,username,team_id FROM users WHERE id=?', (user_id,)).fetchone())


def load_session():
    g.actor, g.csrf, g.session_hash = None, None, None
    db = get_db()
    token = request.cookies.get(COOKIE, '')
    if re.fullmatch(r'[0-9a-f]{64}', token):
        row = db.execute('SELECT * FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()
        if row:
            if time.time() - row['touched'] < current_app.config['SESSION_IDLE_SECONDS']:
                g.session_hash, g.csrf = row['token_hash'], row['csrf']
                if row['user_id']:
                    user = db.execute('SELECT id,username,team_id FROM users WHERE id=?', (row['user_id'],)).fetchone()
                    g.actor = dict(user) if user else None
                db.execute('UPDATE sessions SET touched=? WHERE token_hash=?', (time.time(), digest(token)))
            else:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))
            db.commit()


def status():
    if g.csrf is None:
        new_session()
    return dict(authenticated=g.actor is not None, user=g.actor, csrf_token=g.csrf)


def check_csrf():
    supplied = request.headers.get('X-CSRF-Token', '')
    if not g.csrf or not re.fullmatch(r'[0-9a-f]{64}', supplied) or not secrets.compare_digest(supplied, g.csrf):
        raise DomainError('FORBIDDEN', 'Your session changed. Reload before trying again.', 403)


def protected(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if g.actor is None:
            raise DomainError('UNAUTHENTICATED', 'Please sign in again.', 401)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            check_csrf()
        return function(*args, **kwargs)
    return wrapped


def sign_in(username, password):
    username = string(username, 'username', 3, 64)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', username):
        raise DomainError('VALIDATION_ERROR', 'The username contains unsupported characters.')
    password = string(password, 'password', maximum=128, trim=False)
    check_csrf()
    db = get_db()
    timestamp = time.time()
    address = request.remote_addr or 'local'
    cutoff = timestamp - 900
    db.execute('DELETE FROM login_attempts WHERE attempted<?', (cutoff,))
    failures = db.execute('SELECT COUNT(*) FROM login_attempts WHERE username=? AND address=?',
                          (username, address)).fetchone()[0]
    db.commit()
    if failures >= 5:
        raise DomainError('RATE_LIMITED', 'Too many sign-in attempts. Try again in 15 minutes.', 429)
    user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    valid = check_password_hash(user['password_hash'] if user else _DUMMY_HASH, password)
    if not valid or user is None:
        db.execute('INSERT INTO login_attempts VALUES (?,?,?)', (username, address, timestamp))
        db.commit()
        raise DomainError('UNAUTHENTICATED', 'The username or password is incorrect.', 401)
    db.execute('DELETE FROM login_attempts WHERE username=? AND address=?', (username, address))
    db.execute('DELETE FROM sessions WHERE token_hash=?', (g.session_hash,))
    db.commit()
    new_session(user['id'])
    return status()


def sign_out():
    get_db().execute('DELETE FROM sessions WHERE token_hash=?', (g.session_hash,))
    get_db().commit()
    g.clear_session_cookie = True


def cookie_response(response):
    if getattr(g, 'clear_session_cookie', False):
        response.delete_cookie(COOKIE, httponly=True, samesite='Lax',
                               secure=current_app.config['COOKIE_SECURE'])
    elif getattr(g, 'set_session_token', None):
        response.set_cookie(COOKIE, g.set_session_token, httponly=True, samesite='Lax',
                            secure=current_app.config['COOKIE_SECURE'])
    return response

