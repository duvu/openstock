from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True, slots=True)
class RawOHLCVWindowEvidence:
    row_count: int
    latest_bar_date: str | None


def get_raw_ohlcv_window_evidence(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    lookback_start: str,
    target_date: str,
) -> RawOHLCVWindowEvidence:
    query = (
        "SELECT COUNT(DISTINCT CAST(time AS DATE)), "
        "MAX(CAST(time AS DATE))::VARCHAR "
        "FROM market_ohlcv_raw "
        "WHERE symbol = ? AND interval = '1D' "
        "AND CAST(time AS DATE) >= ? AND CAST(time AS DATE) <= ? "
        "AND LOWER(TRIM(COALESCE(quality_status, ''))) IN ('pass', 'success') "
        "AND (UPPER(TRIM(COALESCE(provider, ''))) <> 'FIINQUANTX' "
        "OR UPPER(TRIM(COALESCE(price_basis, ''))) = 'RAW_UNADJUSTED')"
    )
    row = conn.execute(query, [symbol, lookback_start, target_date]).fetchone()
    return RawOHLCVWindowEvidence(
        row_count=int(row[0]) if row else 0,
        latest_bar_date=str(row[1]) if row and row[1] else None,
    )
