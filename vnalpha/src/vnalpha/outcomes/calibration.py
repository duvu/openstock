"""Deterministic calibration report generator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.outcomes.aggregations import aggregate_all
from vnalpha.outcomes.repositories import (
    get_watchlist_outcome,
    list_risk_flag_performance,
    list_score_bucket_performance,
    list_setup_type_performance,
)

logger = get_logger("outcomes.calibration")


def generate_calibration_report(
    conn: duckdb.DuckDBPyConnection,
    horizon: int,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate deterministic calibration report from aggregate tables.

    Returns a structured dict suitable for rendering.
    """
    if as_of_date is None:
        row = conn.execute(
            "SELECT MAX(watchlist_date)::VARCHAR FROM candidate_outcome WHERE horizon_sessions = ?",
            [horizon],
        ).fetchone()
        as_of_date = row[0] if row and row[0] else "N/A"

    if as_of_date == "N/A":
        return _empty_report(horizon, as_of_date)

    # Score bucket performance
    bucket_rows = list_score_bucket_performance(conn, horizon, as_of_date)

    # Setup type performance
    setup_rows = list_setup_type_performance(conn, horizon, as_of_date)

    # Risk flag performance
    flag_rows = list_risk_flag_performance(conn, horizon, as_of_date)

    # Watchlist outcome summary
    wl_row = get_watchlist_outcome(conn, as_of_date, horizon)
    if wl_row is None and not bucket_rows and not setup_rows and not flag_rows:
        outcome_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM candidate_outcome
            WHERE watchlist_date = ? AND horizon_sessions = ?
            """,
            [as_of_date, horizon],
        ).fetchone()[0]
        if outcome_count:
            aggregate_all(conn, as_of_date, horizon)
            bucket_rows = list_score_bucket_performance(conn, horizon, as_of_date)
            setup_rows = list_setup_type_performance(conn, horizon, as_of_date)
            flag_rows = list_risk_flag_performance(conn, horizon, as_of_date)
            wl_row = get_watchlist_outcome(conn, as_of_date, horizon)

    # Pending/missing counts
    pending_count = 0
    missing_count = 0
    if wl_row:
        pending_count = wl_row.get("pending_count") or 0
        missing_count = wl_row.get("missing_data_count") or 0

    # Score bucket ordering check
    bucket_monotone = _check_bucket_monotonicity(bucket_rows)

    # Best/worst setups
    best_setup = _best_by_return(setup_rows)
    worst_setup = _worst_by_return(setup_rows)

    # Best/worst risk flags
    worst_flag = _worst_by_return(flag_rows)

    report = {
        "as_of_date": as_of_date,
        "horizon_sessions": horizon,
        "score_bucket_performance": bucket_rows,
        "setup_type_performance": setup_rows,
        "risk_flag_performance": flag_rows,
        "score_buckets": bucket_rows,
        "setup_types": setup_rows,
        "risk_flags": flag_rows,
        "watchlist_summary": wl_row,
        "pending_count": pending_count,
        "missing_count": missing_count,
        "score_bucket_monotone": bucket_monotone,
        "best_setup": best_setup,
        "worst_setup": worst_setup,
        "worst_risk_flag": worst_flag,
        "interpretation_note": (
            "Outcome metrics are retrospective research evaluation only. "
            "They are retrospective research evaluation, not trading instructions."
        ),
    }
    return report


def _empty_report(horizon: int, as_of_date: str) -> Dict[str, Any]:
    return {
        "as_of_date": as_of_date,
        "horizon_sessions": horizon,
        "score_bucket_performance": [],
        "setup_type_performance": [],
        "risk_flag_performance": [],
        "score_buckets": [],
        "setup_types": [],
        "risk_flags": [],
        "watchlist_summary": None,
        "pending_count": 0,
        "missing_count": 0,
        "score_bucket_monotone": None,
        "best_setup": None,
        "worst_setup": None,
        "worst_risk_flag": None,
        "interpretation_note": "No outcome data available for retrospective research evaluation.",
    }


def _check_bucket_monotonicity(bucket_rows: List[Dict]) -> Optional[bool]:
    """Return True if higher score buckets have higher avg_forward_return."""
    if len(bucket_rows) < 2:
        return None
    returns = [
        r["avg_forward_return"]
        for r in bucket_rows
        if r["avg_forward_return"] is not None
    ]
    if len(returns) < 2:
        return None
    return all(returns[i] <= returns[i + 1] for i in range(len(returns) - 1))


def _best_by_return(rows: List[Dict]) -> Optional[str]:
    """Return the name/key of the row with highest avg_forward_return."""
    valid = [
        (r, r["avg_forward_return"])
        for r in rows
        if r["avg_forward_return"] is not None
    ]
    if not valid:
        return None
    best = max(valid, key=lambda x: x[1])
    return (
        best[0].get("setup_type")
        or best[0].get("risk_flag")
        or best[0].get("score_bucket")
    )


def _worst_by_return(rows: List[Dict]) -> Optional[str]:
    """Return the name/key of the row with lowest avg_forward_return."""
    valid = [
        (r, r["avg_forward_return"])
        for r in rows
        if r["avg_forward_return"] is not None
    ]
    if not valid:
        return None
    worst = min(valid, key=lambda x: x[1])
    return (
        worst[0].get("setup_type")
        or worst[0].get("risk_flag")
        or worst[0].get("score_bucket")
    )
