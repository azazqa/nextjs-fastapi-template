"""Application domain errors — mapped to HTTP responses in exception_handlers."""


class AppError(Exception):
    """Base domain error with HTTP status and client-safe detail."""

    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(detail, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(detail, status_code=403)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(detail, status_code=404)


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(detail, status_code=409)


class RateLimitError(AppError):
    def __init__(self, detail: str, *, retry_after: int | None = None) -> None:
        super().__init__(detail, status_code=429)
        self.retry_after = retry_after


class RefreshTokenError(UnauthorizedError):
    """Refresh token validation failed."""
