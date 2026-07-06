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
    - For each (symbol, time, interval), pick the row with quality_status='pass',
      preferring the most recently fetched. If no 'pass' row exists, take the
      most recently fetched row regardless.
    - Uses ROW_NUMBER() so NULL fetched_at is handled correctly.

    Returns:
        dict with "upserted" and "rejected" counts.
    """
    symbol_filter = "AND symbol = ?" if symbol else ""  # noqa: F841
    outer_symbol_filter = "AND r.symbol = ?" if symbol else ""

    query = f"""
        INSERT INTO canonical_ohlcv
        (symbol, time, interval, open, high, low, close, volume, selected_provider, quality_status, ingestion_run_id)
        SELECT
            symbol, time, interval, open, high, low, close, volume,
            provider AS selected_provider,
            quality_status,
            ingestion_run_id
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, time, interval
                    ORDER BY
                        CASE WHEN quality_status = 'pass' THEN 0 ELSE 1 END,
                        CASE WHEN fetched_at IS NOT NULL THEN fetched_at ELSE TIMESTAMP '1970-01-01' END DESC,
                        ingestion_run_id DESC
                ) AS rn
            FROM market_ohlcv_raw r
            WHERE r.interval = ?
            {outer_symbol_filter}
        ) ranked
        WHERE rn = 1
        ON CONFLICT (symbol, time, interval) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            selected_provider = excluded.selected_provider,
            quality_status = excluded.quality_status,
            ingestion_run_id = excluded.ingestion_run_id
    """

    # Positional params: one for WHERE interval = ?, optional second for symbol
    params: list = [interval]
    if symbol:
        params.append(symbol)

    try:
        conn.execute(query, params)

        # --- Data quality validation: insert rejected rows for symbols with severe issues ---
        # Check for symbols with invalid canonical data: negative close, high < low
        bad_rows_result = conn.execute(
            f"""
            SELECT symbol, COUNT(*) as bad_count
            FROM canonical_ohlcv
            WHERE interval = ?
              AND (
                  close IS NULL
                  OR close <= 0
                  OR high < low
                  OR volume < 0
              )
            {(" AND symbol = ?" if symbol else "")}
            GROUP BY symbol
            HAVING COUNT(*) > 0
            """,
            [interval] + ([symbol] if symbol else []),
        ).fetchall()

        rejected = 0
        import json as _json
        from datetime import date as _date

        today_str = _date.today().isoformat()
        for bad_symbol, bad_count in bad_rows_result:
            try:
                conn.execute(
                    """
                    INSERT INTO rejected_symbol (symbol, date, stage, reason, details_json, created_at)
                    VALUES (?, ?, 'canonical', 'INVALID_OHLCV', ?, current_timestamp)
                    ON CONFLICT (symbol, date, stage) DO UPDATE SET
                        reason = excluded.reason,
                        details_json = excluded.details_json
                    """,
                    [bad_symbol, today_str, _json.dumps({"bad_rows": bad_count})],
                )
                rejected += 1
            except Exception as e_rej:
                logger.warning(
                    "Failed to insert rejected_symbol for %s: %s", bad_symbol, e_rej
                )

        count_params = [interval]
        count_where = " WHERE interval = ?"
        if symbol:
            count_params.append(symbol)
            count_where += " AND symbol = ?"
        count_result = conn.execute(
            f"SELECT COUNT(*) FROM canonical_ohlcv{count_where}",
            count_params,
        ).fetchone()
        upserted = count_result[0] if count_result else 0
        logger.info(
            "Canonical OHLCV built: upserted=%d rejected=%d symbol=%s interval=%s",
            upserted,
            rejected,
            symbol or "ALL",
            interval,
        )
        return {"upserted": upserted, "rejected": rejected}
    except Exception as e:
        logger.error("build_canonical_ohlcv failed: %s", e)
        raise
