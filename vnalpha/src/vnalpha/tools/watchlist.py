"""watchlist.scan and watchlist.filter tools."""

from __future__ import annotations

from typing import Any

import duckdb

from vnalpha.tools.models import ToolOutput


def scan_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    min_score: float = 0.0,
) -> ToolOutput:
    """Return ranked watchlist candidates for a date."""
    from vnalpha.warehouse.repositories import get_watchlist_rich

    rows = get_watchlist_rich(conn, date)
    if min_score > 0.0:
        rows = [r for r in rows if (r.get("score") or 0) >= min_score]
    return ToolOutput(
        data=rows,
        summary=f"{len(rows)} candidates on {date}",
    )


def filter_watchlist(
    conn: duckdb.DuckDBPyConnection,
    date: str,
    filters: list[dict[str, str]],
) -> ToolOutput:
    """Filter watchlist/candidate_score rows by deterministic conditions.

    Each filter is a dict with keys: key, op, value.
    Supported keys: score, candidate_class, setup_type, rank.

    Raises FilterValidationError if any filter is invalid.
    """
    from vnalpha.tools.filter_validation import FilterValidationError, validate_filters
    from vnalpha.warehouse.repositories import get_candidate_scores

    try:
        validate_filters(filters)
    except FilterValidationError as e:
        return ToolOutput(data=None, summary=str(e), warnings=[str(e)])

    all_scores = get_candidate_scores(conn, date)
    result = _apply_filters(all_scores, filters)
    return ToolOutput(
        data=result,
        summary=f"{len(result)} candidates matching filters on {date}",
    )


def _apply_filters(
    rows: list[dict[str, Any]],
    filters: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Apply filter expressions to a list of dicts."""
    out = []
    for row in rows:
        if _row_matches(row, filters):
            out.append(row)
    return out


# Field alias mapping for user-friendly filter keys
_FIELD_ALIASES: dict[str, str] = {
    "class": "candidate_class",
    "setup": "setup_type",
}


def _row_matches(row: dict[str, Any], filters: list[dict[str, str]]) -> bool:
    for f in filters:
        key = _FIELD_ALIASES.get(f["key"], f["key"])
        op = f["op"]
        raw_val = f["value"]
        row_val = row.get(key)
        if not _check_filter(row_val, op, raw_val):
            return False
    return True


def _check_filter(row_val: Any, op: str, raw_val: str) -> bool:
    """Compare row_val against raw_val using op."""
    # Numeric comparison
    try:
        numeric = float(raw_val)
        rv = float(row_val) if row_val is not None else None
        if rv is None:
            return False
        if op == "=":
            return rv == numeric
        if op == "!=":
            return rv != numeric
        if op == ">":
            return rv > numeric
        if op == ">=":
            return rv >= numeric
        if op == "<":
            return rv < numeric
        if op == "<=":
            return rv <= numeric
    except (ValueError, TypeError):
        pass

    # String comparison
    sv = str(row_val) if row_val is not None else ""
    if op == "=":
        return sv == raw_val
    if op == "!=":
        return sv != raw_val
    if op == "contains":
        return raw_val in sv
    if op == "not_contains":
        return raw_val not in sv
    # Fallback
    return False
