"""Shared date resolver for vnalpha CLI and TUI.

Usage::

    from vnalpha.core.dates import resolve_date

    # Simple: returns Asia/Ho_Chi_Minh today
    date_str = resolve_date("today")      # -> "2026-07-06"
    date_str = resolve_date(None)         # -> "2026-07-06"

    # DB-aware: resolves to latest available watchlist/research date
    date_str = resolve_date("today", conn=conn)   # latest date in daily_watchlist
    date_str = resolve_date(None, conn=conn)

    # Explicit override: always returned as-is (calendar-unaware)
    date_str = resolve_date("2024-01-15") # -> "2024-01-15"
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

import duckdb

if TYPE_CHECKING:
    import duckdb

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_WEEKDAYS = {0, 1, 2, 3, 4}  # Monday=0 … Friday=4


def _today_vn() -> str:
    """Return today's date in Asia/Ho_Chi_Minh timezone as YYYY-MM-DD."""
    return datetime.now(tz=_VN_TZ).strftime("%Y-%m-%d")


def _latest_research_date(conn: "duckdb.DuckDBPyConnection") -> Optional[str]:
    """Return the latest date present in daily_watchlist, or None if empty."""
    try:
        row = conn.execute("SELECT MAX(date)::VARCHAR FROM daily_watchlist").fetchone()
    except duckdb.CatalogException:
        return None
    if row and row[0]:
        return row[0]
    return None


def resolve_date(
    value: Optional[str],
    conn: Optional["duckdb.DuckDBPyConnection"] = None,
) -> str:
    """Resolve a date value to an ISO YYYY-MM-DD string.

    Accepted values:
    - None or "today" → today's date in Asia/Ho_Chi_Minh timezone.
      If *conn* is provided, falls back to the latest available research
      date in daily_watchlist when no data exists for today (e.g. weekends,
      holidays, or data not yet ingested).
    - "YYYY-MM-DD" → validated and returned as-is (explicit override,
      calendar-unaware — no DB lookup performed).

    Raises:
        ValueError: If the value is not a valid ISO date or recognised keyword.
    """
    if value is None or value.strip().lower() == "today":
        today = _today_vn()
        if conn is not None:
            latest = _latest_research_date(conn)
            if latest is not None and latest < today:
                # Latest available data precedes today — likely a weekend,
                # public holiday, or data not yet ingested.  Use latest.
                return latest
        return today

    value = value.strip()
    try:
        from datetime import date

        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date value {value!r}. Expected 'today' or ISO format YYYY-MM-DD."
        ) from exc

    return str(parsed)
