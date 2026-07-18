from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

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
    r"token|password|passwd|secret|authorization|bearer|auth|cookie|credentials?)"
)
_INLINE_DOUBLE_SECRET = re.compile(
    rf'(?i)(?P<prefix>["\']?{_SECRET_FIELD}["\']?\s*[=:]\s*)'
    r'"(?:\\.|[^"\\])*(?:"|\Z)'
)
_INLINE_SINGLE_SECRET = re.compile(
    rf"(?i)(?P<prefix>[\"']?{_SECRET_FIELD}[\"']?\s*[=:]\s*)"
    r"'(?:\\.|[^'\\])*(?:'|\Z)"
)
_QUOTED_AUTHORIZATION_DOUBLE = re.compile(
    r'(?i)(["\']?authorization["\']?\s*[:=]\s*["\']?'
    r'(?:bearer|basic)\s+)"(?:\\.|[^"\\])*(?:"|\Z)'
)
_QUOTED_AUTHORIZATION_SINGLE = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?"
    r"(?:bearer|basic)\s+)'(?:\\.|[^'\\])*(?:'|\Z)"
)
_AUTHORIZATION = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?"
    r"(?:bearer|basic)\s+)[^\"'\s,;}]+"
)
_STANDALONE_BASIC_AUTHORIZATION = re.compile(
    r"(?i)\b(?P<prefix>basic\s+)"
    r"(?P<token>[A-Za-z0-9+/]+={0,2})(?![A-Za-z0-9+/=])"
)
_STANDALONE_BEARER_AUTHORIZATION = re.compile(
    r"(?i)\b(?P<prefix>bearer\s+)"
    r"(?P<token>[A-Za-z0-9._~+/-]+={0,})"
)
_URI = re.compile(r"(?i)\b(?P<scheme>[a-z][a-z0-9+.-]{0,31}://)(?P<body>[^\s]+)")
_TRUNCATED_URI_USERINFO = re.compile(
    r"(?i)\b(?P<scheme>(?:https?|postgres(?:ql)?|mysql|mariadb|mongodb|"
    r"redis(?:s)?|amqp(?:s)?|mssql|sqlserver|oracle)"
    r"(?:\+[a-z0-9._-]+)*://)(?P<authority>[^/?#\s@]+)\Z"
)
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
    r"[A-Za-z0-9_-]*(?![A-Za-z0-9_-])"
)
_TRUNCATED_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r"(?:\.[A-Za-z0-9_-]*)?\Z"
)
_TRUNCATED_JWT_PREFIX = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\Z")
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
        "auth",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "session_id",
        "session_token",
        "passwd",
    }
)
_SENSITIVE_KEY_PREFIXES = _SENSITIVE_KEYS
_SENSITIVE_KEY_VALUE_AFFIXES = frozenset(
    {"data", "hash", "header", "key", "material", "payload", "secret", "token", "value"}
)
_BEARER_PROSE_TERMS = frozenset(
    {
        "bond",
        "bonds",
        "certificate",
        "certificates",
        "debt",
        "instrument",
        "instruments",
        "note",
        "notes",
        "security",
        "securities",
        "share",
        "shares",
    }
)
_MAX_ERROR_SUMMARY_CHARS = 4_096
_MAX_ERROR_SUMMARY_SCAN_CHARS = _MAX_ERROR_SUMMARY_CHARS * 2
_URI_TRAILING_PUNCTUATION = ".,;!?)}>'\"`"


def _redact_standalone_basic(match: re.Match[str], *, scan_truncated: bool) -> str:
    token = match.group("token")
    if scan_truncated and match.end() == len(match.string):
        return f"{match.group('prefix')}[REDACTED]"
    candidates = [token]
    if match.end() == len(match.string):
        candidates.extend(token[:-trim] for trim in range(1, 4) if len(token) > trim)
    for candidate in candidates:
        if len(candidate) % 4 == 1:
            continue
        padded = candidate + ("=" * (-len(candidate) % 4))
        try:
            decoded = base64.b64decode(padded, validate=True)
        except (binascii.Error, ValueError):
            continue
        if b":" in decoded:
            return f"{match.group('prefix')}[REDACTED]"
    return match.group(0)


def _redact_standalone_bearer(match: re.Match[str]) -> str:
    token = match.group("token").removesuffix(".")
    if token.lower() in _BEARER_PROSE_TERMS:
        return match.group(0)
    return f"{match.group('prefix')}[REDACTED]"


def _redact_uri_userinfo(match: re.Match[str]) -> str:
    candidate = match.group(0)
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        body = match.group("body")
        authority_end = min(
            (index for marker in "/?#" if (index := body.find(marker)) >= 0),
            default=len(body),
        )
        authority = body[:authority_end]
        if "@" in authority:
            host = authority.rsplit("@", 1)[1]
            return f"{match.group('scheme')}[REDACTED]@{host}{body[authority_end:]}"
        return candidate
    if parsed.username is None or "@" not in parsed.netloc:
        return candidate
    host = parsed.netloc.rsplit("@", 1)[1]
    suffix = match.group("body")[len(parsed.netloc) :]
    return f"{match.group('scheme')}[REDACTED]@{host}{suffix}"


def _redact_truncated_uri_userinfo(match: re.Match[str]) -> str:
    candidate = match.group(0)
    authority = _strip_authority_punctuation(match.group("authority"))
    removed_chars = len(match.group("authority")) - len(authority)
    endpoint = candidate[:-removed_chars] if removed_chars else candidate
    suffix = candidate[len(endpoint) :]
    if ":" not in authority or (authority.startswith("[") and authority.endswith("]")):
        return candidate
    try:
        parsed = urlsplit(endpoint)
    except ValueError:
        return f"{match.group('scheme')}[REDACTED]{suffix}"
    try:
        port = parsed.port
    except ValueError:
        port = None
    if parsed.hostname and port is not None:
        return candidate
    return f"{match.group('scheme')}[REDACTED]{suffix}"


def _strip_authority_punctuation(authority: str) -> str:
    stripped = authority.rstrip(_URI_TRAILING_PUNCTUATION)
    if stripped.endswith("]") and not (
        stripped.startswith("[") and stripped.count("]") == 1
    ):
        return stripped[:-1]
    return stripped


def is_sensitive_key(key: object) -> bool:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key).strip())
    normalized = re.sub(
        r"_+", "_", camel_split.lower().replace("-", "_").replace(".", "_")
    )
    return (
        normalized in _SENSITIVE_KEYS
        or any(
            normalized.startswith(f"{sensitive}_")
            and normalized.removeprefix(f"{sensitive}_").split("_", 1)[0]
            in _SENSITIVE_KEY_VALUE_AFFIXES
            for sensitive in _SENSITIVE_KEY_PREFIXES
        )
        or any(normalized.endswith(f"_{sensitive}") for sensitive in _SENSITIVE_KEYS)
    )


def sanitize_text(
    value: object, *, strip_rich: bool = True, scan_truncated: bool = False
) -> str:
    text = _TERMINAL_CONTROLS.sub("", str(value))
    if strip_rich:
        text = _RICH_TAGS.sub("", text)
    text = _PEM_PRIVATE_KEY.sub("[REDACTED]", text)
    text = _INLINE_DOUBLE_SECRET.sub(r'\g<prefix>"[REDACTED]"', text)
    text = _INLINE_SINGLE_SECRET.sub(r"\g<prefix>'[REDACTED]'", text)
    text = _QUOTED_AUTHORIZATION_DOUBLE.sub(r'\1"[REDACTED]"', text)
    text = _QUOTED_AUTHORIZATION_SINGLE.sub(r"\1'[REDACTED]'", text)
    text = _AUTHORIZATION.sub(r"\1[REDACTED]", text)
    text = _STANDALONE_BASIC_AUTHORIZATION.sub(
        lambda match: _redact_standalone_basic(match, scan_truncated=scan_truncated),
        text,
    )
    text = _STANDALONE_BEARER_AUTHORIZATION.sub(_redact_standalone_bearer, text)
    text = _URI.sub(_redact_uri_userinfo, text)
    text = _TRUNCATED_URI_USERINFO.sub(_redact_truncated_uri_userinfo, text)
    text = _JWT.sub("[REDACTED]", text)
    text = _TRUNCATED_JWT.sub("[REDACTED]", text)
    if scan_truncated:
        text = _TRUNCATED_JWT_PREFIX.sub("[REDACTED]", text)
    return _INLINE_UNQUOTED_SECRET.sub(r"\1[REDACTED]", text)


def sanitize_error_summary(value: object) -> str:
    value_text = str(value)
    raw = value_text[:_MAX_ERROR_SUMMARY_SCAN_CHARS]
    sanitized = " ".join(
        sanitize_text(
            raw, scan_truncated=len(value_text) > _MAX_ERROR_SUMMARY_SCAN_CHARS
        ).split()
    )
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
