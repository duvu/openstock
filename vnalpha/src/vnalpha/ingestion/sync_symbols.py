"""Sync symbol master from vnstock-service."""
from __future__ import annotations

from typing import Optional
import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    upsert_symbol,
)
from vnalpha.core.logging import get_logger

logger = get_logger("ingestion.sync_symbols")


def sync_symbols(
    conn: duckdb.DuckDBPyConnection,
    client: Optional[VnstockClient] = None,
    source: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Fetch all symbols from vnstock-service and upsert into symbol_master.

    Returns:
        dict with "synced", "errors" counts and "run_id".
    """
    owned = client is None
    if owned:
        client = VnstockClient(base_url=base_url) if base_url else VnstockClient()

    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/reference/symbols",
        universe="ALL",
        params={"source": source} if source else {},
    )

    synced = 0
    errors = 0
    try:
        response = client.get_symbols(source=source)
        for record in response.data:
            try:
                upsert_symbol(
                    conn,
                    symbol=record.get("symbol", ""),
                    exchange=record.get("exchange"),
                    name=record.get("name") or record.get("full_name"),
                    sector=record.get("sector"),
                    industry=record.get("industry"),
                )
                synced += 1
            except Exception as e:
                logger.warning("Failed to upsert symbol %s: %s", record.get("symbol"), e)
                errors += 1

        finish_ingestion_run(conn, run_id, "SUCCESS")
        logger.info("Synced %d symbols, %d errors", synced, errors)
    except Exception as e:
        finish_ingestion_run(conn, run_id, "FAILED", error={"error": str(e)})
        logger.error("sync_symbols failed: %s", e)
        raise
    finally:
        if owned:
            client.close()

    return {"run_id": run_id, "synced": synced, "errors": errors}
