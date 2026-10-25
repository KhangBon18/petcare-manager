class ServiceError(Exception):
    """Expected business-rule failure safe to display to the user."""


class ValidationError(ServiceError):
    def __init__(self, message, *, field=None, field_errors=None):
        super().__init__(message)
        self.field_errors = dict(field_errors or {})
        if field:
            self.field_errors[field] = message


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class ForbiddenError(ServiceError):
    pass


class RateLimitError(ServiceError):
    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))
