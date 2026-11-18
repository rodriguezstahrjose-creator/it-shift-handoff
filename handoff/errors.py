"""Consistent errors shared by HTTP routes and domain services."""
class DomainError(Exception):
    def __init__(self, code, message, status=422, fields=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.fields = fields or {}

