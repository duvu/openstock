from __future__ import annotations

from typing import assert_never

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    IngestionRemediationAction,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.ohlcv_fetch import (
    FetchedOHLCV,
    fetch_ohlcv_for_symbol,
)
from vnalpha.ingestion.persistence import persist_raw_ohlcv_metadata
from vnalpha.ingestion.symbol_outcomes import (
    failed_symbol_result,
    remediation_step,
)
from vnalpha.warehouse.repositories import insert_raw_ohlcv
from vnalpha.warehouse.transaction import warehouse_transaction


def sync_ohlcv_for_symbol(
    conn: duckdb.DuckDBPyConnection,
    client: VnstockClient,
    run_id: str,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1D",
    source: str | None = None,
) -> SymbolIngestionResult:
    outcome = fetch_ohlcv_for_symbol(
        client,
        symbol,
        start=start,
        end=end,
        interval=interval,
        source=source,
    )
    return persist_fetched_ohlcv_for_symbol(
        conn,
        run_id,
        symbol,
        start=start,
        end=end,
        source=source,
        outcome=outcome,
    )


def persist_fetched_ohlcv_for_symbol(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    symbol: str,
    *,
    start: str | None,
    end: str | None,
    source: str | None,
    outcome: FetchedOHLCV | SymbolIngestionResult,
) -> SymbolIngestionResult:
    match outcome:
        case SymbolIngestionResult() as result:
            return result
        case FetchedOHLCV() as fetched:
            return _persist_fetched_ohlcv(
                conn,
                run_id,
                symbol,
                start=start,
                end=end,
                source=source,
                fetched=fetched,
            )
        case unreachable:
            assert_never(unreachable)


def _persist_fetched_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    symbol: str,
    *,
    start: str | None,
    end: str | None,
    source: str | None,
    fetched: FetchedOHLCV,
) -> SymbolIngestionResult:
    try:
        with warehouse_transaction(conn):
            inserted = insert_raw_ohlcv(
                conn,
                run_id=run_id,
                symbol=symbol,
                records=fetched.response.data,
                provider=fetched.provider,
                price_basis=fetched.price_basis,
                quality_status=fetched.response.meta.quality_status,
                fetched_at=fetched.response.meta.fetched_at,
            )
            quality_failed = (fetched.response.meta.quality_status or "").upper() in {
                "ERROR",
                "FAIL",
                "FAILED",
                "INVALID",
            }
            remediation = remediation_step(
                symbol,
                start,
                end,
                source,
                IngestionRemediationAction.INSPECT_DIAGNOSTICS_AND_RETRY,
                "Inspect the provider quality report, correct the data, then retry.",
            )
            result = SymbolIngestionResult(
                symbol=symbol,
                status=(
                    SymbolIngestionStatus.INVALID
                    if quality_failed
                    else SymbolIngestionStatus.SUCCESS
                ),
                requested_start=start,
                requested_end=end,
                provider=fetched.provider,
                rows_received=len(fetched.response.data),
                rows_inserted=inserted,
                error_category=(
                    IngestionErrorCategory.PROVIDER_DATA if quality_failed else None
                ),
                diagnostics_ref=fetched.response.meta.request_id,
                message=(
                    "Provider quality validation failed." if quality_failed else None
                ),
                remediation=(
                    f"{remediation.guidance} {remediation.render_command()}"
                    if quality_failed
                    else None
                ),
                remediation_steps=((remediation,) if quality_failed else ()),
                quality_report=fetched.quality_report,
                diagnostics=fetched.diagnostics,
                attempts=fetched.attempts,
            )
            persist_raw_ohlcv_metadata(conn, run_id, result)
    except duckdb.Error:
        return failed_symbol_result(
            symbol,
            start,
            end,
            fetched.provider,
            IngestionErrorCategory.STORAGE,
            False,
            "Warehouse persistence failed.",
            fetched.attempts,
        )
    return result


__all__ = ["persist_fetched_ohlcv_for_symbol", "sync_ohlcv_for_symbol"]
