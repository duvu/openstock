"""Redaction helpers for auth-layer safe logging and output.

Provides utilities to redact sensitive credential material from strings
and dicts before they are logged, printed, or returned to callers.

Usage::

    from vnstock.core.auth.redaction import redact, redact_dict

    safe_msg = redact("Bearer eyJhbGciOiJIUzI1NiJ9.abc123")
    # -> "Bearer [REDACTED]"

    clean = redact_dict({"token": "abc", "provider": "TCBS"})
    # -> {"token": "[REDACTED]", "provider": "TCBS"}
"""

from __future__ import annotations

import re
from typing import Any

#: Fields whose values should always be redacted in dicts.
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "secret",
        "authorization",
        "bearer",
        "cookie",
        "session_id",
        "otp_session",
        "otpsession",
        "credential",
        "private_key",
    }
)

#: Regex patterns that indicate sensitive content in string values.
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    # JWT token: three base64url segments separated by dots
    re.compile(
        r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
        re.IGNORECASE,
    ),
    # Bearer token in header values
    re.compile(r"Bearer\s+[A-Za-z0-9\._\-]+", re.IGNORECASE),
    # Basic auth base64
    re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE),
]

_REDACTED = "[REDACTED]"


def redact(value: str) -> str:
    """Redact sensitive patterns from a string value.

    Replaces JWT tokens and Bearer/Basic patterns with ``[REDACTED]``.

    Args:
        value: String to sanitize.

    Returns:
        Sanitized string with sensitive patterns replaced.
    """
    result = value
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result


def redact_dict(data: dict[str, Any], *, deep: bool = True) -> dict[str, Any]:
    """Return a copy of *data* with sensitive field values redacted.

    Keys matching :data:`_SENSITIVE_KEYS` (case-insensitive) have their values
    replaced with ``"[REDACTED]"``.

    Args:
        data: Source dict to sanitize.
        deep: If ``True``, recurse into nested dicts and lists.

    Returns:
        New dict with sensitive values replaced.
    """
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_KEYS:
            result[k] = _REDACTED
        elif deep and isinstance(v, dict):
            result[k] = redact_dict(v, deep=deep)
        elif deep and isinstance(v, list):
            result[k] = _redact_list(v)
        else:
            result[k] = v
    return result


def _redact_list(items: list[Any]) -> list[Any]:
    """Recursively redact sensitive values in a list."""
    sanitized = []
    for item in items:
        if isinstance(item, dict):
            sanitized.append(redact_dict(item))
        elif isinstance(item, list):
            sanitized.append(_redact_list(item))
        else:
            sanitized.append(item)
    return sanitized


def is_sensitive_key(key: str) -> bool:
    """Return whether *key* is considered sensitive.

    Args:
        key: Dict key name to check.

    Returns:
        ``True`` if the key is in the sensitive keys set.
    """
    return key.lower() in _SENSITIVE_KEYS
