"""Data availability checks — read-only queries against the warehouse."""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime, timedelta, timezone
from typing import Optional

import duckdb


def get_symbol_master_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
) -> bool:
    """Return True if the symbol exists in symbol_master (active or inactive)."""
    row = conn.execute(
        "SELECT 1 FROM symbol_master WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    return row is not None


def get_canonical_ohlcv_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    lookback_start: str,
) -> int:
    """Return number of canonical OHLCV bars for the symbol in [lookback_start, target_date]."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM canonical_ohlcv
        WHERE symbol = ?
          AND interval = '1D'
          AND CAST(time AS DATE) >= ?
          AND CAST(time AS DATE) <= ?
        """,
        [symbol, lookback_start, target_date],
    ).fetchone()
    return row[0] if row else 0


def get_benchmark_status(
    conn: duckdb.DuckDBPyConnection,
    benchmark: str,
    target_date: str,
    lookback_start: str,
) -> int:
    """Return number of canonical OHLCV bars for benchmark in [lookback_start, target_date]."""
    return get_canonical_ohlcv_status(conn, benchmark, target_date, lookback_start)


def get_feature_snapshot_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
) -> bool:
    """Return True if a feature_snapshot row exists for (symbol, date)."""
    row = conn.execute(
        "SELECT 1 FROM feature_snapshot WHERE symbol = ? AND date = ? LIMIT 1",
        [symbol, target_date],
    ).fetchone()
    return row is not None


def get_candidate_score_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    target_date: str,
    stale_after_calendar_days: int = 7,
) -> Optional[str]:
    """Return candidate_class if a fresh candidate_score exists, else None.

    A score is considered stale if the feature_data lineage bar_date (as_of_bar_date
    in lineage_json) is more than *stale_after_calendar_days* before target_date.
    In practice, for intra-session freshness we only check existence — the stale
    threshold guards against day-old pipeline runs.
    """
    row = conn.execute(
        """
        SELECT candidate_class, lineage_json
        FROM candidate_score
        WHERE symbol = ? AND date = ?
        LIMIT 1
        """,
        [symbol, target_date],
    ).fetchone()
    if row is None:
        return None
    candidate_class, lineage_raw = row

    # Check staleness based on as_of_bar_date in lineage
    if lineage_raw and stale_after_calendar_days > 0:
        import json as _json

        try:
            lineage = (
                _json.loads(lineage_raw)
                if isinstance(lineage_raw, str)
                else lineage_raw
            )
            as_of_bar_date = lineage.get("as_of_bar_date") or lineage.get(
                "feature_date"
            )
            if as_of_bar_date:
                bar_dt = _parse_date(as_of_bar_date)
                target_dt = _parse_date(target_date)
                if bar_dt and target_dt:
                    delta = (target_dt - bar_dt).days
                    if delta > stale_after_calendar_days:
                        return None  # stale
        except Exception:  # noqa: BLE001
            pass

    return candidate_class


def _parse_date(s: str) -> Optional[DateType]:
    """Parse YYYY-MM-DD string to date, returning None on failure."""
    try:
        return DateType.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def compute_lookback_start(target_date: str, lookback_days: int) -> str:
    """Compute the lookback start date as YYYY-MM-DD string."""
    try:
        target_dt = DateType.fromisoformat(target_date)
    except (ValueError, TypeError):
        target_dt = datetime.now(timezone.utc).date()
    lookback_dt = target_dt - timedelta(days=lookback_days)
    return lookback_dt.isoformat()
