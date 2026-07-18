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
_SECRET_FIELD = (
    r"(?:api[_-]?key|access[_-]?key|access[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|private[_-]?key|refresh[_-]?token|session[_-]?token|"
    r"token|password|passwd|secret|authorization|cookie|credentials?)"
)
_INLINE_DOUBLE_SECRET = re.compile(
    rf'(?i)(?P<prefix>["\']?{_SECRET_FIELD}["\']?\s*[=:]\s*)'
    r'"(?:\\.|[^"\\])*(?:"|\Z)'
)
_INLINE_SINGLE_SECRET = re.compile(
    rf"(?i)(?P<prefix>[\"']?{_SECRET_FIELD}[\"']?\s*[=:]\s*)"
    r"'(?:\\.|[^'\\])*(?:'|\Z)"
)
_AUTHORIZATION = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?"
    r"(?:bearer|basic)\s+)[^\"'\s,;}]+"
)
_URI_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]{1,31}://)[^/\s@]+@")
_TRUNCATED_URI_USERINFO = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]{1,31}://)[^:/\s@]+:[^/\s@]+\Z"
)
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
    r"[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)
_TRUNCATED_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r"(?:\.[A-Za-z0-9_-]*)?\Z"
)
_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN ((?:[A-Z0-9]+ )?PRIVATE KEY)-----.*?"
    r"(?:-----END \1-----|\Z)",
    re.DOTALL,
)
_INLINE_UNQUOTED_SECRET = re.compile(
    rf"(?i)([\"']?{_SECRET_FIELD}[\"']?\s*[=:]\s*)(?![\"'])"
    r"[^\s,;}]+"
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
_MAX_ERROR_SUMMARY_CHARS = 4_096
_MAX_ERROR_SUMMARY_SCAN_CHARS = _MAX_ERROR_SUMMARY_CHARS * 2


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_").replace(".", "_")
    return normalized in _SENSITIVE_KEYS or any(
        normalized.endswith(f"_{sensitive}") for sensitive in _SENSITIVE_KEYS
    )


def sanitize_text(value: object, *, strip_rich: bool = True) -> str:
    text = _TERMINAL_CONTROLS.sub("", str(value))
    if strip_rich:
        text = _RICH_TAGS.sub("", text)
    text = _PEM_PRIVATE_KEY.sub("[REDACTED]", text)
    text = _INLINE_DOUBLE_SECRET.sub(r'\g<prefix>"[REDACTED]"', text)
    text = _INLINE_SINGLE_SECRET.sub(r"\g<prefix>'[REDACTED]'", text)
    text = _AUTHORIZATION.sub(r"\1[REDACTED]", text)
    text = _URI_USERINFO.sub(r"\1[REDACTED]@", text)
    text = _TRUNCATED_URI_USERINFO.sub(r"\1[REDACTED]", text)
    text = _JWT.sub("[REDACTED]", text)
    text = _TRUNCATED_JWT.sub("[REDACTED]", text)
    return _INLINE_UNQUOTED_SECRET.sub(r"\1[REDACTED]", text)


def sanitize_error_summary(value: object) -> str:
    raw = str(value)[:_MAX_ERROR_SUMMARY_SCAN_CHARS]
    sanitized = " ".join(sanitize_text(raw).split())
    return sanitized[:_MAX_ERROR_SUMMARY_CHARS].rstrip()


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
