"""Date parsing boundary for data provisioning."""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime, timezone


class InvalidEnsureDateError(ValueError):
    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(value)

    def __str__(self) -> str:
        return f"Invalid target date {self.value!r}; expected YYYY-MM-DD or 'today'."


def normalize_explicit_date(value: str) -> str:
    """Parse an explicitly supplied ISO calendar date without fallback."""

    normalized = value.strip()
    try:
        parsed = DateType.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidEnsureDateError(value=value) from exc
    if parsed.isoformat() != normalized:
        raise InvalidEnsureDateError(value=value)
    return normalized


def normalize_optional_date(value: str | None, *, today: DateType | None = None) -> str:
    """Resolve an omitted or explicit ``today`` value, otherwise parse strictly."""

    if value is None or value.strip().lower() == "today":
        resolved = today or datetime.now(timezone.utc).date()
        return resolved.isoformat()
    return normalize_explicit_date(value)


__all__ = [
    "InvalidEnsureDateError",
    "normalize_explicit_date",
    "normalize_optional_date",
]
