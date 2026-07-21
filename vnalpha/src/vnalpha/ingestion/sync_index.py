"""Sync index/benchmark OHLCV from vnstock-service.

Design (Design Area 2, Option A):
- Explicit `vnalpha sync index --symbol VNINDEX --start 2024-01-01` command.
- Uses VnstockClient.get_index_ohlcv() to fetch index OHLCV.
- Stores in market_ohlcv_raw using the same schema as equity OHLCV.
- build_canonical promotes it to canonical_ohlcv.
"""

from __future__ import annotations

import json
from typing import Optional

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.core.logging import get_logger
from vnalpha.ingestion.persistence import (
    bind_ingestion_run_correlation,
    persistence_diagnostics,
    validated_ohlcv_price_basis,
)
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
)
from vnalpha.warehouse.transaction import warehouse_transaction

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
    source = validate_persistence_source(source)
    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()
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
    bind_ingestion_run_correlation(conn, run_id)

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
        if response.meta.dataset != "index.ohlcv":
            raise ValueError("Provider returned an unexpected index dataset.")
        provider = response.meta.provider.strip().upper()
        actual_source = validate_persistence_source(provider)
        if source is not None and actual_source != source:
            raise ValueError(
                "Index provider did not match the explicitly selected source."
            )
        quality_status = (response.meta.quality_status or "").strip().upper()
        if quality_status not in {"PASS", "SUCCESS"}:
            raise ValueError("Index provider quality did not pass.")
        price_basis = validated_ohlcv_price_basis(provider, response.diagnostics)
        diagnostics = persistence_diagnostics(
            response.meta.provider, response.diagnostics
        )
        quality_report_json = (
            json.dumps(response.meta.quality_report)
            if response.meta.quality_report
            else None
        )
        diagnostics_json = (
            json.dumps(diagnostics, sort_keys=True) if diagnostics else None
        )
        with warehouse_transaction(conn):
            inserted = insert_raw_ohlcv(
                conn,
                run_id=run_id,
                symbol=symbol,
                records=response.data,
                provider=provider,
                price_basis=price_basis,
                quality_status=response.meta.quality_status,
                fetched_at=response.meta.fetched_at,
            )
            conn.execute(
                "UPDATE market_ohlcv_raw SET quality_report_json = ?, "
                "diagnostics_json = ? WHERE ingestion_run_id = ? AND symbol = ?",
                [quality_report_json, diagnostics_json, run_id, symbol],
            )
            if inserted == 0:
                skipped = 1
            finish_ingestion_run(conn, run_id, "SUCCESS" if inserted else "EMPTY")
        logger.info(
            "Index OHLCV sync complete: symbol=%s inserted=%d", symbol, inserted
        )
    except Exception as e:
        finish_ingestion_run(
            conn,
            run_id,
            "FAILED",
            error={"error": "Index OHLCV sync failed."},
        )
        logger.error("Failed to sync index OHLCV for %s: %s", symbol, type(e).__name__)
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
