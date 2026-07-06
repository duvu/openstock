"""Build canonical OHLCV from raw ingestion data."""
from __future__ import annotations

from typing import Optional
import duckdb

from vnalpha.core.logging import get_logger

logger = get_logger("ingestion.build_canonical")


def build_canonical_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: Optional[str] = None,
    interval: str = "1D",
) -> dict:
    """Promote raw OHLCV to canonical_ohlcv with deduplication.

    Strategy:
    - For each (symbol, time, interval), pick the row with the most recent
      fetched_at from market_ohlcv_raw where quality_status != 'fail'.
    - If no 'pass' rows exist, take the latest row regardless.

    Returns:
        dict with "upserted" count.
    """
    where_clause = "AND r.interval = ?"
    params: list = [interval]

    if symbol:
        where_clause += " AND r.symbol = ?"
        params.append(symbol)

    query = f"""
        INSERT OR REPLACE INTO canonical_ohlcv
        (symbol, time, interval, open, high, low, close, volume, selected_provider, quality_status, ingestion_run_id)
        SELECT
            r.symbol,
            r.time,
            r.interval,
            r.open,
            r.high,
            r.low,
            r.close,
            r.volume,
            r.provider AS selected_provider,
            r.quality_status,
            r.ingestion_run_id
        FROM market_ohlcv_raw r
        INNER JOIN (
            SELECT
                symbol,
                time,
                interval,
                MAX(CASE WHEN quality_status = 'pass' THEN fetched_at ELSE NULL END) AS best_pass_ts,
                MAX(fetched_at) AS latest_ts
            FROM market_ohlcv_raw
            WHERE interval = ?
            {('AND symbol = ?' if symbol else '')}
            GROUP BY symbol, time, interval
        ) best ON r.symbol = best.symbol AND r.time = best.time AND r.interval = best.interval
        WHERE r.fetched_at = COALESCE(best.best_pass_ts, best.latest_ts)
        {where_clause}
    """

    # Params for inner SELECT and outer WHERE
    inner_params: list = [interval]
    if symbol:
        inner_params.append(symbol)
    all_params = inner_params + params

    try:
        conn.execute(query, all_params)
        count_result = conn.execute(
            "SELECT COUNT(*) FROM canonical_ohlcv" + (" WHERE symbol = ? AND interval = ?" if symbol else " WHERE interval = ?"),
            ([symbol, interval] if symbol else [interval]),
        ).fetchone()
        upserted = count_result[0] if count_result else 0
        logger.info("Canonical OHLCV built: upserted=%d symbol=%s interval=%s", upserted, symbol or "ALL", interval)
        return {"upserted": upserted}
    except Exception as e:
        logger.error("build_canonical_ohlcv failed: %s", e)
        raise
