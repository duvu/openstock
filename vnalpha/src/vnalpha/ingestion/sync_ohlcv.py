"""Sync equity OHLCV from vnstock-service."""
from __future__ import annotations

from typing import List, Optional

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.core.logging import get_logger
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
    insert_raw_ohlcv,
)

logger = get_logger("ingestion.sync_ohlcv")


def sync_ohlcv_for_symbol(
    conn: duckdb.DuckDBPyConnection,
    client: VnstockClient,
    run_id: str,
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
    source: Optional[str] = None,
) -> int:
    """Fetch OHLCV for one symbol and insert raw rows. Returns inserted count."""
    try:
        response = client.get_equity_ohlcv(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            source=source,
        )
        return insert_raw_ohlcv(
            conn,
            run_id=run_id,
            symbol=symbol,
            records=response.data,
            provider=response.meta.provider,
            quality_status=response.meta.quality_status,
            fetched_at=response.meta.fetched_at,
        )
    except Exception as e:
        logger.warning("Failed to sync OHLCV for %s: %s", symbol, e)
        return 0


def sync_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    universe: Optional[List[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
    source: Optional[str] = None,
    client: Optional[VnstockClient] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Sync OHLCV for all symbols in universe.

    If universe is None, reads active symbols from symbol_master.

    Returns:
        dict with "total", "inserted", "skipped" counts and "run_id".
    """
    owned = client is None
    if owned:
        client = VnstockClient(base_url=base_url) if base_url else VnstockClient()

    if universe is None:
        universe = get_symbols_active(conn)

    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/equity/ohlcv",
        universe=f"{len(universe)}_symbols",
        params={"start": start, "end": end, "interval": interval, "source": source},
    )

    total = len(universe)
    inserted = 0
    skipped = 0

    try:
        for symbol in universe:
            count = sync_ohlcv_for_symbol(
                conn, client, run_id, symbol,
                start=start, end=end, interval=interval, source=source,
            )
            if count > 0:
                inserted += count
            else:
                skipped += 1

        finish_ingestion_run(conn, run_id, "SUCCESS")
        logger.info("OHLCV sync complete: total=%d inserted=%d skipped=%d", total, inserted, skipped)
    except Exception as e:
        finish_ingestion_run(conn, run_id, "FAILED", error={"error": str(e)})
        raise
    finally:
        if owned:
            client.close()

    return {"run_id": run_id, "total": total, "inserted": inserted, "skipped": skipped}
