"""Classify SimpleFIN Bridge API errors for user-facing messages."""


def _error_text(err: dict | str) -> tuple[str, str]:
    if isinstance(err, dict):
        return (
            str(err.get("code") or "").lower(),
            str(err.get("msg") or err.get("message") or "").lower(),
        )
    text = str(err).lower()
    return "", text


def is_rate_limit_error(err: dict | str) -> bool:
    code, msg = _error_text(err)
    if code in ("gen.api",):
        return True
    keywords = (
        "fewer requests",
        "24 requests per day",
        "refreshed once every 24",
        "rate limit",
    )
    return any(k in msg for k in keywords)


def filter_connection_errors(errors: list | None) -> list:
    if not errors:
        return []
    return [e for e in errors if not is_rate_limit_error(e)]


def has_rate_limit_error(errors: list | None) -> bool:
    if not errors:
        return False
    return any(is_rate_limit_error(e) for e in errors)
