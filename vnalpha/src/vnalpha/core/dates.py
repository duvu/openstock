"""Shared date resolver for vnalpha CLI and TUI.

Usage::

    from vnalpha.core.dates import resolve_date

    date_str = resolve_date("today")     # -> "2024-01-15" (current date)
    date_str = resolve_date("2024-01-15") # -> "2024-01-15"
    date_str = resolve_date(None)        # -> "2024-01-15" (current date)
"""

from __future__ import annotations

from datetime import date


def resolve_date(value: str | None) -> str:
    """Resolve a date value to an ISO YYYY-MM-DD string.

    Accepted values:
    - None or "today" → today's date
    - "YYYY-MM-DD" → validated and returned as-is

    Raises:
        ValueError: If the value is not a valid ISO date or recognised keyword.
    """
    if value is None or value.strip().lower() == "today":
        return str(date.today())

    value = value.strip()
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date value {value!r}. Expected 'today' or ISO format YYYY-MM-DD."
        ) from exc

    return str(parsed)
