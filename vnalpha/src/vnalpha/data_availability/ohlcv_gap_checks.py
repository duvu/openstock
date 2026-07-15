"""Read-only readiness queries over persisted OHLCV gap observations."""

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True, slots=True)
class UnresolvedTrueGapWindow:
    """Inclusive daily OHLCV readiness window for one symbol."""

    symbol: str
    lookback_start: str
    target_date: str
    interval: str = "1D"


def count_unresolved_true_gaps(
    conn: duckdb.DuckDBPyConnection,
    window: UnresolvedTrueGapWindow,
) -> int:
    """Return unresolved published OHLCV gaps inside one readiness window."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM ohlcv_gap_observation
        WHERE symbol = ?
          AND interval = ?
          AND gap_kind = 'TRUE_GAP'
          AND resolved_at IS NULL
          AND session_date BETWEEN ? AND ?
        """,
        [
            window.symbol,
            window.interval,
            window.lookback_start,
            window.target_date,
        ],
    ).fetchone()
    return row[0] if row else 0
