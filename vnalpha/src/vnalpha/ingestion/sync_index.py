"""Sync index/benchmark OHLCV from vnstock-service.

Design (Design Area 2, Option A):
- Explicit `vnalpha sync index --symbol VNINDEX --start 2024-01-01` command.
- Uses VnstockClient.get_index_ohlcv() to fetch index OHLCV.
- Stores in market_ohlcv_raw using the same schema as equity OHLCV.
- build_canonical promotes it to canonical_ohlcv.
"""

from __future__ import annotations

from typing import Optional

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.core.logging import get_logger
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
)

logger = get_logger("ingestion.sync_index")


def sync_index_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: str = "VNINDEX",
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
    source: Optional[str] = None,
    client: Optional[VnstockClient] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Fetch index OHLCV and store in market_ohlcv_raw with provider lineage.

    The same build_canonical step promotes index data to canonical_ohlcv,
    so `build canonical` covers both equity and index symbols.

    Returns:
        dict with "symbol", "inserted", "skipped", "run_id".
    """
    owned = client is None
    if owned:
        client = VnstockClient(base_url=base_url) if base_url else VnstockClient()

    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/index/ohlcv",
        universe=symbol,
        params={"start": start, "end": end, "interval": interval, "source": source},
    )

    inserted = 0
    skipped = 0

    try:
        response = client.get_index_ohlcv(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            source=source,
        )
        inserted = insert_raw_ohlcv(
            conn,
            run_id=run_id,
            symbol=symbol,
            records=response.data,
            provider=response.meta.provider,
            quality_status=response.meta.quality_status,
            fetched_at=response.meta.fetched_at,
        )
        if inserted == 0:
            skipped = 1

        finish_ingestion_run(conn, run_id, "SUCCESS")
        logger.info(
            "Index OHLCV sync complete: symbol=%s inserted=%d", symbol, inserted
        )
    except Exception as e:
        finish_ingestion_run(conn, run_id, "FAILED", error={"error": str(e)})
        logger.error("Failed to sync index OHLCV for %s: %s", symbol, e)
        if owned:
            client.close()
        raise
    finally:
        if owned:
            client.close()

    return {
        "run_id": run_id,
        "symbol": symbol,
        "inserted": inserted,
        "skipped": skipped,
    }
