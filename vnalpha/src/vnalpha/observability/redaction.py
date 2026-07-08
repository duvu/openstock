"""Redaction module — sanitise sensitive runtime values before logging.

Content modes (read from VNALPHA_LOG_CONTENT_MODE env):
  metadata  — only shape/type/IDs/counts; no content
  redacted  — content after redaction (default)
  full      — raw content, explicit opt-in only
"""

from __future__ import annotations

import os
import re

# ---------------------------------------------------------------------------
# Sensitive key patterns (case-insensitive substring match)
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS: tuple[str, ...] = (
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "private_key",
    "access_key",
    "passwd",
)

# Regex to match secret-like values in free-text strings
_SECRET_VALUE_RE = re.compile(
    r"(password|token|secret|api[_-]?key|apikey|authorization|bearer"
    r"|private[_-]?key|access[_-]?key|passwd)"
    r"\s*[=:]\s*\S+",
    re.IGNORECASE,
)

_REDACTED_PLACEHOLDER = "[REDACTED]"
_REDACTED_STATUS = "redacted"
_FULL_STATUS = "full"
_METADATA_STATUS = "metadata"

# Safe metadata-only keys (used in metadata mode)
_METADATA_SAFE_KEYS: frozenset[str] = frozenset(
    {
        "event_id",
        "run_id",
        "created_at",
        "level",
        "event_type",
        "surface",
        "correlation_id",
        "span_id",
        "parent_span_id",
        "status",
        "duration_ms",
        "exit_code",
        "started_at",
        "ended_at",
        "module",
        "function",
        "operation",
        "error_type",
        "stacktrace_hash",
        "redaction_status",
        "actor",
        "command",
    }
)


def get_content_mode() -> str:
    """Return the configured content mode (default: redacted)."""
    raw = os.environ.get("VNALPHA_LOG_CONTENT_MODE", "redacted").strip().lower()
    if raw in {"full", "metadata", "redacted"}:
        return raw
    return "redacted"


def _is_sensitive_key(key: str) -> bool:
    low = key.lower()
    return any(pat in low for pat in SENSITIVE_PATTERNS)


def redact_dict(d: dict, mode: str | None = None) -> dict:
    """Return a sanitised copy of *d* according to *mode*.

    metadata: keep only safe metadata keys
    redacted: replace values of sensitive keys with [REDACTED]
    full:     return as-is (explicit opt-in)
    """
    if mode is None:
        mode = get_content_mode()
    if mode == "full":
        return dict(d)
    if mode == "metadata":
        return {k: v for k, v in d.items() if k in _METADATA_SAFE_KEYS}
    # redacted (default)
    result: dict = {}
    for k, v in d.items():
        if _is_sensitive_key(k):
            result[k] = _REDACTED_PLACEHOLDER
        elif isinstance(v, dict):
            result[k] = redact_dict(v, mode)
        elif isinstance(v, str):
            result[k] = redact_str(v, mode)
        else:
            result[k] = v
    return result


def redact_str(s: str, mode: str | None = None) -> str:
    """Regex-replace secret-looking patterns in *s*.

    In metadata or redacted mode, replaces «key=value» pairs where the key
    matches a sensitive pattern.  In full mode returns *s* unchanged.
    """
    if mode is None:
        mode = get_content_mode()
    if mode == "full":
        return s
    return _SECRET_VALUE_RE.sub(
        lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]",
        s,
    )


def redaction_status(mode: str | None = None) -> str:
    """Return the redaction_status label for a given mode."""
    resolved = mode or get_content_mode()
    if resolved == "full":
        return _FULL_STATUS
    if resolved == "metadata":
        return _METADATA_STATUS
    return _REDACTED_STATUS
