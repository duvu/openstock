"""Sync symbol master from vnstock-service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.core.logging import get_logger
from vnalpha.ingestion.symbol_taxonomy import normalize_symbol_taxonomy
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
)
from vnalpha.warehouse.symbol_lifecycle import (
    complete_symbol_source_snapshot,
    deactivate_unseen_symbols,
    persist_symbol_taxonomy,
    start_symbol_source_snapshot,
)

logger = get_logger("ingestion.sync_symbols")


def sync_symbols(
    conn: duckdb.DuckDBPyConnection,
    client: Optional[VnstockClient] = None,
    source: Optional[str] = None,
    base_url: Optional[str] = None,
    authoritative_snapshot: bool = False,
) -> dict[str, int | str]:
    """Sync a lifecycle/taxonomy snapshot from vnstock-service.

    Only a complete snapshot explicitly marked authoritative may deactivate
    unseen symbols from the same source. Partial and failed runs retain the
    prior active universe.
    """
    source = validate_persistence_source(source)
    owned = client is None
    if owned:
        client = VnstockClient(base_url=base_url) if base_url else VnstockClient()

    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()
    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/reference/symbols",
        universe="ALL",
        params={"source": source} if source else {},
    )

    snapshot_source = source or "vnstock-service"
    start_symbol_source_snapshot(
        conn,
        run_id,
        snapshot_source,
        authoritative_snapshot,
        get_correlation_id(),
    )
    log_audit(
        "SYMBOL_SNAPSHOT_STARTED",
        "Symbol lifecycle snapshot started.",
        extra={
            "authoritative": authoritative_snapshot,
            "snapshot_id": run_id,
            "source": snapshot_source,
        },
    )
    synced = 0
    errors = 0
    observed = 0
    deactivated = 0
    transaction_started = False
    try:
        response = client.get_symbols(source=source)
        response_meta = getattr(response, "meta", None)
        response_dataset = str(getattr(response_meta, "dataset", "")).strip()
        if response_dataset != "reference.symbols":
            raise ValueError("unexpected symbol dataset")
        response_source = validate_persistence_source(
            str(getattr(response_meta, "provider", ""))
        )
        if response_source is None:
            raise ValueError("symbol provider must not be empty")
        if source is not None and response_source != source:
            raise ValueError("symbol provider did not match the selected source")
        response_quality = (
            str(getattr(response_meta, "quality_status", "") or "").strip().upper()
        )
        if response_quality not in {"PASS", "SUCCESS"}:
            raise ValueError("symbol provider quality did not pass")
        if not response.data:
            raise ValueError("symbol source response is empty")
        conn.execute("BEGIN TRANSACTION")
        transaction_started = True
        if snapshot_source != response_source:
            snapshot_source = response_source
            conn.execute(
                "UPDATE symbol_source_snapshot SET source = ? WHERE snapshot_id = ?",
                [snapshot_source, run_id],
            )
        for record in response.data:
            observed += 1
            try:
                if not isinstance(record, Mapping):
                    raise ValueError("Symbol source record must be an object.")
                taxonomy = normalize_symbol_taxonomy(record, snapshot_source)
                persist_symbol_taxonomy(
                    conn,
                    run_id,
                    taxonomy,
                )
                synced += 1
            except (TypeError, ValueError) as error:
                logger.warning("Failed to persist source symbol: %s", error)
                errors += 1

        snapshot_status = "SUCCESS" if errors == 0 else "PARTIAL"
        if authoritative_snapshot and snapshot_status == "SUCCESS":
            deactivated = deactivate_unseen_symbols(conn, run_id, snapshot_source)
        complete_symbol_source_snapshot(
            conn,
            run_id,
            snapshot_status,
            observed,
            synced,
            errors,
            deactivated,
        )
        finish_ingestion_run(conn, run_id, snapshot_status)
        conn.execute("COMMIT")
        transaction_started = False
        log_audit(
            "SYMBOL_SNAPSHOT_COMPLETED",
            "Symbol lifecycle snapshot completed.",
            extra={
                "deactivated": deactivated,
                "errors": errors,
                "snapshot_id": run_id,
                "snapshot_status": snapshot_status,
                "synced": synced,
            },
        )
        logger.info(
            "Synced %d symbols, %d errors, %d deactivated", synced, errors, deactivated
        )
    except Exception:  # noqa: BLE001
        if transaction_started:
            conn.execute("ROLLBACK")
            transaction_started = False
        complete_symbol_source_snapshot(
            conn, run_id, "FAILED", observed, synced, errors, deactivated
        )
        finish_ingestion_run(conn, run_id, "FAILED", error={"stage": "symbol_snapshot"})
        log_audit(
            "SYMBOL_SNAPSHOT_FAILED",
            "Symbol lifecycle snapshot failed.",
            status="FAILED",
            extra={"snapshot_id": run_id, "source": snapshot_source},
        )
        logger.error("Symbol lifecycle snapshot failed.")
        raise
    finally:
        if owned:
            client.close()

    return {
        "deactivated": deactivated,
        "errors": errors,
        "run_id": run_id,
        "snapshot_id": run_id,
        "snapshot_status": snapshot_status,
        "synced": synced,
    }
