"""Resolve the effective persisted research date for TUI read surfaces."""

from __future__ import annotations

from vnalpha.core.dates import resolve_date
from vnalpha.warehouse.connection import get_connection


def resolve_tui_research_date(requested_date: str | None) -> str:
    """Return the requested date or the latest persisted research date."""

    if requested_date is not None and requested_date.strip().lower() != "today":
        return resolve_date(requested_date)
    with get_connection() as connection:
        return resolve_date(requested_date, conn=connection)
