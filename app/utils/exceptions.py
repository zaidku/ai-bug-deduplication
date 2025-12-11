"""
Custom exception classes
"""


class BugDeduplicationError(Exception):
    """Base exception for the application"""
    status_code = 500
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.__class__.__name__
        rv['message'] = self.message
        return rv


class ValidationError(BugDeduplicationError):
    """Validation failed"""
    status_code = 400


class AuthenticationError(BugDeduplicationError):
    """Authentication failed"""
    status_code = 401


class AuthorizationError(BugDeduplicationError):
    """Authorization failed"""
    status_code = 403


class ResourceNotFoundError(BugDeduplicationError):
    """Resource not found"""
    status_code = 404


class DuplicateResourceError(BugDeduplicationError):
    """Resource already exists"""
    status_code = 409


class RateLimitError(BugDeduplicationError):
    """Rate limit exceeded"""
    status_code = 429


class ExternalServiceError(BugDeduplicationError):
    """External service (Jira, TP) error"""
    status_code = 502


class DatabaseError(BugDeduplicationError):
    """Database operation failed"""
    status_code = 500


class AIProcessingError(BugDeduplicationError):
    """AI/ML processing error"""
    status_code = 500
