from __future__ import annotations

from datetime import date, timedelta

import duckdb

from vnalpha.ingestion.trading_calendar import SessionRange, VietnamSessionCalendar


def tail_start(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    symbol: str,
    resolved_date: str,
    initial_start: str,
) -> str | None:
    latest = conn.execute(
        f"SELECT MAX(CAST(time AS DATE))::VARCHAR FROM {table} "
        "WHERE symbol = ? AND interval = '1D'",
        [symbol],
    ).fetchone()
    if latest is None or latest[0] is None:
        return initial_start
    if str(latest[0]) >= resolved_date:
        return None
    sessions = VietnamSessionCalendar().sessions(
        SessionRange(
            start=date.fromisoformat(str(latest[0])) + timedelta(days=1),
            end=date.fromisoformat(resolved_date),
        )
    )
    return sessions[0].isoformat() if sessions else None


def canonical_lineage(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple[str | None, str | None]:
    row = conn.execute(
        """
        SELECT selected_provider, ingestion_run_id
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D'
          AND CAST(time AS DATE) BETWEEN ? AND ?
        ORDER BY time DESC
        LIMIT 1
        """,
        [symbol, start_date, end_date],
    ).fetchone()
    if row is None:
        return None, None
    return (
        str(row[0]) if row[0] is not None else None,
        str(row[1]) if row[1] is not None else None,
    )
