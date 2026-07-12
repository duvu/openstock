from __future__ import annotations

import re
from dataclasses import dataclass

from vnalpha.workspace_context.models import JsonDict


@dataclass(frozen=True, slots=True)
class RedactedValue:
    text: str
    status: str
    matched_categories: tuple[str, ...]


_SENSITIVE_VALUE_RE = re.compile(
    r"(?P<category>password|token|secret|api[_-]?key|apikey|authorization|bearer|private[_-]?key|access[_-]?key|passwd)"
    r"\s*[=:]\s*\S+",
    re.IGNORECASE,
)
_SENSITIVE_KEY_PARTS = (
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


def redact_workspace_text(text: str) -> RedactedValue:
    categories: list[str] = []
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        category = match.group("category").lower().replace("-", "_")
        if category not in seen:
            seen.add(category)
            categories.append(category)
        return f"{match.group('category')}=[REDACTED]"

    return RedactedValue(
        text=_SENSITIVE_VALUE_RE.sub(replace, text),
        status="redacted",
        matched_categories=tuple(categories),
    )


def redact_workspace_mapping(values: JsonDict) -> JsonDict:
    redacted: JsonDict = {}
    for key, value in values.items():
        if isinstance(value, str) and any(
            part in key.lower() for part in _SENSITIVE_KEY_PARTS
        ):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, str):
            redacted[key] = redact_workspace_text(value).text
        elif isinstance(value, dict):
            redacted[key] = redact_workspace_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_workspace_text(item).text if isinstance(item, str) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted
