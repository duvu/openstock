"""Support and resistance extraction from canonical OHLCV bars."""

from __future__ import annotations

import duckdb


class LevelExtractor:
    """Derive observable price levels without forecasting future prices."""

    def extract(
        self,
        conn: duckdb.DuckDBPyConnection,
        symbol: str,
        date: str,
    ) -> list[dict[str, float | str]]:
        rows = conn.execute(
            """
            SELECT high, low, close
            FROM canonical_ohlcv
            WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?
            ORDER BY time DESC
            LIMIT 60
            """,
            [symbol, date],
        ).fetchall()
        if not rows:
            return []
        highs = [float(row[0]) for row in rows if row[0] is not None]
        lows = [float(row[1]) for row in rows if row[1] is not None]
        closes = [float(row[2]) for row in rows if row[2] is not None]
        if not highs or not lows or not closes:
            return []
        return [
            {
                "type": "RESISTANCE",
                "value": max(highs),
                "strength": "OBSERVED_60D_HIGH",
                "derivation": "highest canonical high across available trailing bars",
            },
            {
                "type": "SUPPORT",
                "value": min(lows),
                "strength": "OBSERVED_60D_LOW",
                "derivation": "lowest canonical low across available trailing bars",
            },
            {
                "type": "REFERENCE_CLOSE",
                "value": closes[0],
                "strength": "LATEST_CLOSE",
                "derivation": "latest canonical close on or before as-of date",
            },
        ]
