"""Sync equity OHLCV from vnstock-service."""

from __future__ import annotations

from dataclasses import replace

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.core.logging import get_logger
from vnalpha.ingestion.models import (
    OHLCVBatchResult,
    SymbolIngestionResult,
    aggregate_ohlcv_results,
)
from vnalpha.ingestion.persistence import (
    bind_ingestion_run_correlation,
    persist_ohlcv_batch_result,
)
from vnalpha.ingestion.symbol_sync import sync_ohlcv_for_symbol
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
)

logger = get_logger("ingestion.sync_ohlcv")


def sync_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    universe: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1D",
    source: str | None = None,
    client: VnstockClient | None = None,
    base_url: str | None = None,
) -> OHLCVBatchResult:
    """Sync OHLCV for all symbols in universe.

    If universe is None, reads active symbols from symbol_master.

    Returns a typed batch with per-symbol outcomes and terminal status.
    """
    source = validate_persistence_source(source)
    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()
    if universe is None:
        universe = get_symbols_active(conn)

    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/equity/ohlcv",
        universe=f"{len(universe)}_symbols",
        params={"start": start, "end": end, "interval": interval, "source": source},
    )
    bind_ingestion_run_correlation(conn, run_id)

    results: list[SymbolIngestionResult] = []
    active_client = client
    owned = False

    try:
        if active_client is None:
            active_client = (
                VnstockClient(base_url=base_url) if base_url else VnstockClient()
            )
            owned = True
        for symbol in universe:
            result = sync_ohlcv_for_symbol(
                conn,
                active_client,
                run_id,
                symbol,
                start=start,
                end=end,
                interval=interval,
                source=source,
            )
            if result.diagnostics_ref is None:
                result = replace(
                    result,
                    diagnostics_ref=f"ingestion:{run_id}:{symbol}",
                )
            results.append(result)

        batch = aggregate_ohlcv_results(run_id, tuple(results))
        persist_ohlcv_batch_result(conn, batch)
        logger.info(
            "OHLCV sync complete: status=%s total=%d inserted=%d",
            batch.status.value,
            batch.requested_count,
            batch.rows_inserted,
        )
        return batch
    except Exception as exc:
        logger.exception("OHLCV batch failed before completion for run_id=%s", run_id)
        finish_ingestion_run(
            conn,
            run_id,
            "FAILED",
            error={
                "error": "OHLCV batch failed before completion.",
                "cause": type(exc).__name__,
            },
        )
        raise
    finally:
        if owned and active_client is not None:
            active_client.close()
