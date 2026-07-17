from __future__ import annotations

import json

import duckdb

from vnalpha.ingestion.models import (
    BatchIngestionStatus,
    OHLCVBatchResult,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.observability.context import get_correlation_id

_SAFE_PROVIDER_LINEAGE_KEYS = frozenset(
    {
        "sdk_version",
        "contract_version",
        "source_method",
        "source_query",
        "snapshot_semantics",
    }
)
_SAFE_OHLCV_POLICY_KEYS = frozenset(
    {"adjusted", "basis", "lasted", "mode", "start", "end"}
)
RAW_UNADJUSTED_PRICE_BASIS = "RAW_UNADJUSTED"


def bind_ingestion_run_correlation(
    conn: duckdb.DuckDBPyConnection, run_id: str
) -> None:
    conn.execute(
        "UPDATE ingestion_run SET correlation_id = ? WHERE ingestion_run_id = ?",
        [get_correlation_id(), run_id],
    )


def persistence_diagnostics(
    provider: str, diagnostics: dict[str, object]
) -> dict[str, object]:
    if provider.upper() != "FIINQUANTX":
        return dict(diagnostics)
    raw_lineage = diagnostics.get("provider_lineage", {})
    if not isinstance(raw_lineage, dict):
        raw_lineage = {}
    safe_lineage: dict[str, object] = {
        key: value
        for key, value in raw_lineage.items()
        if key in _SAFE_PROVIDER_LINEAGE_KEYS
        and isinstance(value, (str, int, float, bool))
    }
    raw_policy = raw_lineage.get("ohlcv_request_policy")
    if isinstance(raw_policy, dict):
        safe_policy = {
            key: value
            for key, value in raw_policy.items()
            if key in _SAFE_OHLCV_POLICY_KEYS
            and (isinstance(value, (str, int, float, bool)) or value is None)
        }
        if safe_policy:
            safe_lineage["ohlcv_request_policy"] = safe_policy
    return {"provider_lineage": safe_lineage}


def validated_ohlcv_price_basis(provider: str, diagnostics: dict[str, object]) -> str:
    safe_diagnostics = persistence_diagnostics(provider, diagnostics)
    lineage = safe_diagnostics.get("provider_lineage", {})
    policy = (
        lineage.get("ohlcv_request_policy", {}) if isinstance(lineage, dict) else {}
    )
    basis = policy.get("basis") if isinstance(policy, dict) else None
    if basis is None and provider.strip().upper() != "FIINQUANTX":
        return RAW_UNADJUSTED_PRICE_BASIS
    if basis != RAW_UNADJUSTED_PRICE_BASIS:
        raise ValueError(
            "Canonical OHLCV persistence requires verified RAW_UNADJUSTED basis."
        )
    return RAW_UNADJUSTED_PRICE_BASIS


def persist_raw_ohlcv_metadata(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    result: SymbolIngestionResult,
) -> None:
    if result.rows_inserted == 0:
        return
    conn.execute(
        """
        UPDATE market_ohlcv_raw
        SET quality_report_json = ?, diagnostics_json = ?
        WHERE ingestion_run_id = ? AND symbol = ?
        """,
        [
            json.dumps(result.quality_report) if result.quality_report else None,
            json.dumps(result.diagnostics) if result.diagnostics else None,
            run_id,
            result.symbol,
        ],
    )


def persist_ohlcv_batch_result(
    conn: duckdb.DuckDBPyConnection, batch: OHLCVBatchResult
) -> None:
    failed_symbols = [
        result.symbol
        for result in batch.symbol_results
        if result.status is SymbolIngestionStatus.FAILED
    ]
    empty_symbols = [
        result.symbol
        for result in batch.symbol_results
        if result.status is SymbolIngestionStatus.EMPTY
    ]
    invalid_symbols = [
        result.symbol
        for result in batch.symbol_results
        if result.status is SymbolIngestionStatus.INVALID
    ]
    quality_reports = {
        result.symbol: result.quality_report
        for result in batch.symbol_results
        if result.quality_report
    }
    diagnostics = {
        result.symbol: result.diagnostics
        for result in batch.symbol_results
        if result.diagnostics
    }
    error = None
    if batch.status is not BatchIngestionStatus.SUCCESS:
        error = json.dumps(
            {
                "terminal_reason": batch.terminal_reason,
                "failed_symbols": failed_symbols,
                "empty_symbols": empty_symbols,
                "invalid_symbols": invalid_symbols,
            }
        )
    conn.execute(
        """
        UPDATE ingestion_run
        SET finished_at = current_timestamp,
            status = ?,
            error_json = ?,
            requested_count = ?,
            success_count = ?,
            empty_count = ?,
            failed_count = ?,
            invalid_count = ?,
            skipped_count = ?,
            failed_symbols_json = ?,
            symbol_results_json = ?,
            quality_report_json = ?,
            diagnostics_json = ?,
            terminal_reason = ?,
            correlation_id = ?
        WHERE ingestion_run_id = ?
        """,
        [
            batch.status.value,
            error,
            batch.requested_count,
            batch.count(SymbolIngestionStatus.SUCCESS),
            batch.count(SymbolIngestionStatus.EMPTY),
            batch.count(SymbolIngestionStatus.FAILED),
            batch.count(SymbolIngestionStatus.INVALID),
            batch.count(SymbolIngestionStatus.SKIPPED),
            json.dumps(failed_symbols),
            json.dumps([result.to_payload() for result in batch.symbol_results]),
            json.dumps(quality_reports) if quality_reports else None,
            json.dumps(diagnostics) if diagnostics else None,
            batch.terminal_reason,
            get_correlation_id(),
            batch.run_id,
        ],
    )
