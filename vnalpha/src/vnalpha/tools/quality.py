"""quality.get_status tool."""

from __future__ import annotations

import duckdb

from vnalpha.tools.models import ToolOutput


def get_quality_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None = None,
    date: str | None = None,
) -> ToolOutput:
    """Return data quality status for a symbol or the latest watchlist."""
    if symbol:
        # Symbol-level quality: latest canonical_ohlcv quality_status
        rows = conn.execute(
            """
            SELECT symbol, time, quality_status, selected_provider
            FROM canonical_ohlcv
            WHERE symbol = ? AND interval = '1D'
            ORDER BY time DESC
            LIMIT 5
            """,
            [symbol],
        ).fetchall()
        if not rows:
            return ToolOutput(
                data=None,
                summary=f"No canonical data found for {symbol}.",
                warnings=["Run 'vnalpha build canonical' first."],
            )
        data = [
            {
                "symbol": r[0],
                "time": str(r[1]),
                "quality_status": r[2] or "unknown",
                "provider": r[3],
            }
            for r in rows
        ]
        return ToolOutput(data=data, summary=f"Quality status for {symbol} (last {len(data)} bars).")
    else:
        # Watchlist-level: aggregate quality across latest watchlist
        date_clause = f"= '{date}'" if date else "= (SELECT MAX(date) FROM daily_watchlist)"
        rows = conn.execute(
            f"""
            SELECT dw.symbol, co.quality_status, co.selected_provider
            FROM daily_watchlist dw
            LEFT JOIN (
                SELECT symbol, quality_status, selected_provider,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) AS rn
                FROM canonical_ohlcv WHERE interval = '1D'
            ) co ON co.symbol = dw.symbol AND co.rn = 1
            WHERE dw.date {date_clause}
            ORDER BY dw.rank
            """
        ).fetchall()
        data = [
            {"symbol": r[0], "quality_status": r[1] or "unknown", "provider": r[2]}
            for r in rows
        ]
        return ToolOutput(data=data, summary=f"{len(data)} watchlist symbols quality check.")
