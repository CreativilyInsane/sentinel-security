# backend/app/utils/errors.py
class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 400, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)

class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)

class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)

class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)

class BadRequestError(AppException):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=400)