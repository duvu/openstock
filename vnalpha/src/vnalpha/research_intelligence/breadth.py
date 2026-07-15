"""Exact-date market breadth calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb

from vnalpha.warehouse.repositories import get_symbols_active

MINIMUM_BREADTH_ROWS = 5


@dataclass(frozen=True, slots=True)
class BreadthContext:
    active_count: int
    eligible_count: int
    excluded_count: int
    coverage: float | None
    pct_above_ma20: float | None
    pct_above_ma50: float | None
    pct_positive_return20: float | None
    excluded_symbols: tuple[str, ...]

    @property
    def available(self) -> bool:
        """Whether enough exact, usable features exist for breadth metrics."""
        return self.eligible_count >= MINIMUM_BREADTH_ROWS


def load_breadth_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    benchmark_symbol: str,
) -> BreadthContext:
    """Calculate breadth from active symbols with exact-date usable features."""
    symbols = tuple(
        symbol for symbol in get_symbols_active(conn) if symbol != benchmark_symbol
    )
    usable_rows: list[tuple[float, float, float, float]] = []
    exclusions: list[str] = []
    for symbol in symbols:
        row = conn.execute(
            """
            SELECT close, ma20, ma50, return_20d
            FROM feature_snapshot
            WHERE symbol = ? AND date = ? AND as_of_bar_date = ?
              AND feature_data_status = 'EXACT_DATE'
              AND feature_profile IN ('MINIMAL_20', 'STANDARD_120', 'FULL_252')
              AND neutral_completeness = 'COMPLETE'
              AND close IS NOT NULL AND ma20 IS NOT NULL AND ma50 IS NOT NULL
              AND return_20d IS NOT NULL
            """,
            [symbol, as_of_date, as_of_date],
        ).fetchone()
        if row is None:
            exclusions.append(symbol)
            continue
        usable_rows.append((float(row[0]), float(row[1]), float(row[2]), float(row[3])))
    active_count = len(symbols)
    eligible_count = len(usable_rows)
    excluded_count = len(exclusions)
    coverage = eligible_count / active_count if active_count else None
    if eligible_count < MINIMUM_BREADTH_ROWS:
        return BreadthContext(
            active_count=active_count,
            eligible_count=eligible_count,
            excluded_count=excluded_count,
            coverage=coverage,
            pct_above_ma20=None,
            pct_above_ma50=None,
            pct_positive_return20=None,
            excluded_symbols=tuple(exclusions),
        )
    return BreadthContext(
        active_count=active_count,
        eligible_count=eligible_count,
        excluded_count=excluded_count,
        coverage=coverage,
        pct_above_ma20=sum(close > ma20 for close, ma20, _, _ in usable_rows)
        / eligible_count,
        pct_above_ma50=sum(close > ma50 for close, _, ma50, _ in usable_rows)
        / eligible_count,
        pct_positive_return20=sum(return20 > 0 for _, _, _, return20 in usable_rows)
        / eligible_count,
        excluded_symbols=tuple(exclusions),
    )
