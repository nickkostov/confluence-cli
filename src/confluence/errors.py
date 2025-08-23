class ConfluenceError(Exception):
    """Base exception for Confluence-related errors."""


class AuthError(ConfluenceError):
    """401/403 authentication or authorization failure."""


class NotFound(ConfluenceError):
    """404 resource not found (space, page, parent)."""


class Conflict(ConfluenceError):
    """409 conflict, e.g., duplicate title or version conflict."""


class RateLimited(ConfluenceError):
    """429 rate limit exceeded. Server may send Retry-After header."""


class ServerError(ConfluenceError):
    """5xx server-side error."""


class ValidationError(ConfluenceError):
    """Client-side validation error before calling the API."""


def raise_for_status(status_code: int, message: str = "", payload: dict | None = None):
    detail = message or ""
    if payload:
        err_title = payload.get("message") or payload.get("title") or ""
        err_reason = payload.get("reason") or ""
        if err_title or err_reason:
            detail = f"{detail} {err_title} {err_reason}".strip()

    if status_code in (401, 403):
        raise AuthError(detail)
    if status_code == 404:
        raise NotFound(detail)
    if status_code == 409:
        raise Conflict(detail)
    if status_code == 429:
        raise RateLimited(detail)
    if 500 <= status_code < 600:
        raise ServerError(detail)
    if 400 <= status_code < 500:
        raise ValidationError(detail)
