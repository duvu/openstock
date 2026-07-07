"""quality.get_status and quality.get_many_status tools."""

from __future__ import annotations

import duckdb

from vnalpha.tools.models import ToolOutput


def get_quality_status(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None = None,
    date: str | None = None,
) -> ToolOutput:
    """Return data quality status for a symbol or the latest watchlist.

    When ``symbol`` is given, returns quality rows where canonical_ohlcv.time
    is on or before ``date`` (defaults to latest available bar).

    When ``symbol`` is None, returns quality for the watchlist on ``date``
    (defaults to the latest watchlist date). The join is date-bounded so that
    only OHLCV bars on or before the watchlist date are considered.
    """
    if symbol:
        # Symbol-level quality: use as-of-date aware lookup
        if date:
            rows = conn.execute(
                """
                SELECT symbol, time, quality_status, selected_provider
                FROM canonical_ohlcv
                WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?
                ORDER BY time DESC
                LIMIT 5
                """,
                [symbol, date],
            ).fetchall()
        else:
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
            suffix = f" as of {date}" if date else ""
            return ToolOutput(
                data=None,
                summary=f"No canonical data found for {symbol}{suffix}.",
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
        # Attach rejected records when available
        if date:
            rejected_rows = conn.execute(
                """
                SELECT stage, reason, details_json, date
                FROM rejected_symbol
                WHERE symbol = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 10
                """,
                [symbol, date],
            ).fetchall()
        else:
            rejected_rows = conn.execute(
                """
                SELECT stage, reason, details_json, date
                FROM rejected_symbol
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 10
                """,
                [symbol],
            ).fetchall()
        rejected = [
            {
                "stage": r[0],
                "reason": r[1],
                "details": r[2],
                "date": str(r[3]),
            }
            for r in rejected_rows
        ]
        result: dict = {
            "quality_rows": data,
            "rejected_records": rejected,
        }
        return ToolOutput(
            data=result,
            summary=f"Quality status for {symbol} (last {len(data)} bars"
            + (f" up to {date}" if date else "")
            + f", {len(rejected)} rejected records).",
        )
    else:
        # Watchlist-level: join OHLCV bars on or before the watchlist date
        if date:
            wl_date_clause = "= ?"
            wl_params: list = [date]
        else:
            wl_date_clause = "= (SELECT MAX(date) FROM daily_watchlist)"
            wl_params = []
        rows = conn.execute(
            f"""
            SELECT dw.symbol, co.quality_status, co.selected_provider
            FROM daily_watchlist dw
            LEFT JOIN (
                SELECT symbol, quality_status, selected_provider,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol ORDER BY time DESC
                    ) AS rn,
                    CAST(time AS DATE) AS bar_date
                FROM canonical_ohlcv WHERE interval = '1D'
            ) co ON co.symbol = dw.symbol
                AND co.rn = 1
                AND co.bar_date <= dw.date
            WHERE dw.date {wl_date_clause}
            ORDER BY dw.rank
            """,
            wl_params,
        ).fetchall()
        data = [
            {"symbol": r[0], "quality_status": r[1] or "unknown", "provider": r[2]}
            for r in rows
        ]
        return ToolOutput(
            data=data, summary=f"{len(data)} watchlist symbols quality check."
        )


def get_many_quality_status(
    conn: duckdb.DuckDBPyConnection,
    symbols: list[str],
    date: str | None = None,
) -> ToolOutput:
    """Return data quality status for multiple symbols.

    Each symbol is evaluated for OHLCV bars on or before ``date``
    (defaults to the latest available bar for each symbol independently).
    Returns one quality record per symbol (most recent bar).
    """
    if not symbols:
        return ToolOutput(data=[], summary="No symbols provided.")

    placeholders = ", ".join(["?"] * len(symbols))
    if date:
        rows = conn.execute(
            f"""
            SELECT symbol, MAX(CAST(time AS DATE)) AS as_of_date,
                   MAX(quality_status) AS quality_status,
                   MAX(selected_provider) AS provider
            FROM (
                SELECT symbol, time, quality_status, selected_provider,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) AS rn
                FROM canonical_ohlcv
                WHERE symbol IN ({placeholders})
                  AND interval = '1D'
                  AND CAST(time AS DATE) <= ?
            ) sub
            WHERE rn = 1
            GROUP BY symbol
            """,
            symbols + [date],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT symbol, CAST(time AS DATE) AS as_of_date,
                   quality_status, selected_provider
            FROM (
                SELECT symbol, time, quality_status, selected_provider,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) AS rn
                FROM canonical_ohlcv
                WHERE symbol IN ({placeholders})
                  AND interval = '1D'
            ) sub
            WHERE rn = 1
            """,
            symbols,
        ).fetchall()

    found = {r[0] for r in rows}
    missing = [s for s in symbols if s not in found]
    data = [
        {
            "symbol": r[0],
            "as_of_date": str(r[1]) if r[1] else None,
            "quality_status": r[2] or "unknown",
            "provider": r[3],
        }
        for r in rows
    ]
    warnings = [f"No canonical data for: {', '.join(missing)}"] if missing else []
    suffix = f" as of {date}" if date else ""
    return ToolOutput(
        data=data,
        summary=f"Quality status for {len(data)}/{len(symbols)} symbols{suffix}.",
        warnings=warnings,
    )
