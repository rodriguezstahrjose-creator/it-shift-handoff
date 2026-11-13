"""Strict JSON contracts; bool is deliberately not accepted as an integer."""
import re
from uuid import UUID
from flask import request
from .errors import DomainError


def body(required=(), optional=()):
    if request.mimetype != 'application/json':
        raise DomainError('UNSUPPORTED_MEDIA_TYPE', 'Use application/json.', 415)
    value = request.get_json(silent=True)
    return fields(value, required, optional)


def fields(value, required=(), optional=()):
    if not isinstance(value, dict):
        raise DomainError('INVALID_JSON', 'A JSON object is required.', 400)
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise DomainError('VALIDATION_ERROR', 'Check the request fields.', fields={
            **{k: 'This field is required.' for k in missing},
            **{k: 'Unknown field.' for k in unknown}})
    return value


def string(value, name, minimum=1, maximum=5000, trim=True):
    if not isinstance(value, str):
        raise DomainError('VALIDATION_ERROR', 'A text value is required.', fields={name: 'Enter text.'})
    result = value.strip() if trim else value
    if not minimum <= len(result) <= maximum:
        raise DomainError('VALIDATION_ERROR', 'Check the text length.', fields={
            name: f'Enter between {minimum} and {maximum} characters.'})
    return result


def integer(value, name, minimum=1, maximum=2**31-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DomainError('VALIDATION_ERROR', 'Check the number.', fields={
            name: f'Enter a whole number from {minimum} to {maximum}.'})
    return value


def uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise DomainError('VALIDATION_ERROR', 'A canonical UUID is required.') from None
    return value


def page():
    if request.args.keys() - {'after_seq', 'limit'}:
        raise DomainError('VALIDATION_ERROR', 'Unknown pagination parameter.')
    result = []
    for name, default, low, high in [('after_seq', '0', 0, 2**31-1), ('limit', '25', 1, 100)]:
        values = request.args.getlist(name)
        raw = values[0] if values else default
        if len(values) > 1 or not re.fullmatch(r'[0-9]{1,10}', raw):
            raise DomainError('VALIDATION_ERROR', 'Invalid pagination parameter.')
        result.append(integer(int(raw), name, low, high))
    return result

