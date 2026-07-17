from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_TERMINAL_CONTROLS = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))|[\x00-\x08\x0b-\x1f\x7f-\x9f]"
)
_RICH_TAGS = re.compile(
    r"\[/?(?:bold|dim|italic|underline|blink|reverse|strike|black|red|green|yellow|blue|magenta|cyan|white|default|bright_(?:black|red|green|yellow|blue|magenta|cyan|white)|on (?:black|red|green|yellow|blue|magenta|cyan|white|default))\]",
    re.IGNORECASE,
)
_AUTHORIZATION = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+")
_INLINE_SECRET = re.compile(
    r"(?i)((?:['\"]?(?:api[_-]?key|access[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|refresh[_-]?token|session[_-]?token|token|password|secret|authorization|cookie|credentials?)['\"]?\s*[=:]\s*)['\"]?)[^\s,;}'\"]+"
)
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "access_token",
        "auth_token",
        "client_secret",
        "refresh_token",
        "token",
        "password",
        "private_key",
        "secret",
        "authorization",
        "authorization_header",
        "cookie",
        "credential",
        "credentials",
        "session_id",
        "session_token",
    }
)


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_").replace(".", "_")
    return normalized in _SENSITIVE_KEYS or any(
        normalized.endswith(f"_{sensitive}") for sensitive in _SENSITIVE_KEYS
    )


def sanitize_text(value: object, *, strip_rich: bool = True) -> str:
    text = _TERMINAL_CONTROLS.sub("", str(value))
    if strip_rich:
        text = _RICH_TAGS.sub("", text)
    text = _AUTHORIZATION.sub(r"\1[REDACTED]", text)
    return _INLINE_SECRET.sub(r"\1[REDACTED]", text)


def redact_structure(value: Any, *, depth: int = 0) -> Any:
    if depth > 10:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            sanitize_text(key): (
                "[REDACTED]"
                if is_sensitive_key(key)
                else redact_structure(item, depth=depth + 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_structure(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value
