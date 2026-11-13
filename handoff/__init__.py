"""Application factory for the CMSC 495 solo Alpha."""
import os
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from . import auth, db
from .errors import DomainError


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.environ.get('HANDOFF_DATABASE', str(Path(app.instance_path) / 'handoff.sqlite')),
        MAX_CONTENT_LENGTH=64 * 1024, SESSION_IDLE_SECONDS=1800, RANK_TIMEOUT=4,
        COOKIE_SECURE=os.environ.get('HANDOFF_HTTPS') == '1',
        TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'])
    if config:
        app.config.update(config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    app.extensions['rank_lock'] = threading.Lock()
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def prepare():
        g.request_id = str(uuid4())
        if request.path.startswith('/api/'):
            auth.load_session()

    @app.after_request
    def finish(response):
        auth.cookie_response(response)
        response.headers.update({
            'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'same-origin', 'Cache-Control': 'no-store',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; "
                                       "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'X-Request-ID': getattr(g, 'request_id', str(uuid4()))})
        return response

    @app.errorhandler(DomainError)
    def domain_error(error):
        return jsonify(error=dict(code=error.code, message=error.message, fields=error.fields,
                                   request_id=g.request_id)), error.status

    @app.errorhandler(sqlite3.Error)
    def storage_error(_error):
        return domain_error(DomainError('STORAGE_UNAVAILABLE', 'Storage is unavailable. Please try again.', 503))

    @app.errorhandler(HTTPException)
    def http_error(error):
        names = {413: 'PAYLOAD_TOO_LARGE', 404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED'}
        return domain_error(DomainError(names.get(error.code, 'INVALID_REQUEST'),
                                       error.description, error.code))

    @app.errorhandler(Exception)
    def unexpected(error):
        # Log the exception type and request ID, never payloads or raw exceptions.
        app.logger.error('request=%s exception=%s', g.request_id, type(error).__name__)
        return domain_error(DomainError('INTERNAL_ERROR', 'An unexpected error occurred.', 500))

    from .routes import api, web
    app.register_blueprint(api)
    app.register_blueprint(web)
    return app

