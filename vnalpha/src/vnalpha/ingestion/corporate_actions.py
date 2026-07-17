"""Bounded corporate-action ingestion, revisioning and reconciliation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import duckdb

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import VnstockClientError, VnstockHTTPError
from vnalpha.clients.vnstock.source_policy import validate_persistence_source
from vnalpha.ingestion.corporate_action_reconciliation import _ingest_record
from vnalpha.warehouse.repositories import create_ingestion_run, finish_ingestion_run


def sync_corporate_actions(
    conn: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    source: str | None = None,
    client: VnstockClient | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch, preserve and reconcile corporate-action evidence for one symbol."""
    symbol = symbol.strip().upper()
    owned = client is None
    if owned:
        client = VnstockClient(base_url=base_url) if base_url else VnstockClient()
    run_id = create_ingestion_run(
        conn,
        source_service="vnstock-service",
        source_endpoint="/v1/reference/corporate-actions",
        universe=symbol,
        params={"symbol": symbol, "start": start, "end": end, "source": source},
    )
    counts = {
        "observed": 0,
        "raw_inserted": 0,
        "canonical_inserted": 0,
        "unchanged": 0,
        "revised": 0,
        "conflicts": 0,
        "quarantined": 0,
        "affected_ranges": 0,
    }
    try:
        response = client.get_corporate_actions(
            symbol=symbol, start=start, end=end, source=source
        )
        if response.meta.dataset != "reference.corporate_actions":
            raise ValueError("Unexpected corporate-action dataset.")
        provider = validate_persistence_source(str(response.meta.provider))
        if provider is None:
            raise ValueError("Corporate-action provider must not be empty.")
        requested_source = validate_persistence_source(source)
        if requested_source is not None and provider != requested_source:
            raise ValueError("Corporate-action provider did not match selected source.")
        quality_status = (response.meta.quality_status or "").strip().upper()
        if quality_status not in {"PASS", "SUCCESS"}:
            raise ValueError("Corporate-action provider quality did not pass.")
        conn.execute("BEGIN TRANSACTION")
        for record in response.data:
            counts["observed"] += 1
            record_outcome = _ingest_record(
                conn,
                run_id=run_id,
                provider=provider,
                requested_symbol=symbol,
                record=record,
            )
            counts[record_outcome.outcome] += 1
            counts["raw_inserted"] += int(record_outcome.raw_inserted)
            counts["conflicts"] += int(record_outcome.conflict)
            counts["affected_ranges"] += int(record_outcome.affected)
        status = (
            "EMPTY"
            if counts["observed"] == 0
            else "COMPLETE"
            if counts["quarantined"] == 0 and counts["conflicts"] == 0
            else "PARTIAL"
        )
        _persist_run_outcome(conn, run_id=run_id, status=status, counts=counts)
        finish_ingestion_run(conn, run_id, status)
        conn.execute("COMMIT")
        return {"run_id": run_id, "status": status, **counts}
    except VnstockHTTPError as exc:
        try:
            conn.execute("ROLLBACK")
        except duckdb.Error:
            pass
        unsupported = exc.status_code == 404 and "unsupported" in exc.body.lower()
        status = "UNSUPPORTED" if unsupported else "FAILED"
        error = {
            "stage": "corporate_actions",
            "type": type(exc).__name__,
            "status_code": exc.status_code,
        }
        _persist_run_outcome(
            conn, run_id=run_id, status=status, counts=counts, error=error
        )
        finish_ingestion_run(conn, run_id, status, error=error)
        return {
            "run_id": run_id,
            "status": status,
            "error": "Provider does not support corporate actions."
            if unsupported
            else "Corporate-action provider request failed.",
            **counts,
        }
    except VnstockClientError as exc:
        try:
            conn.execute("ROLLBACK")
        except duckdb.Error:
            pass
        error = {"stage": "corporate_actions", "type": type(exc).__name__}
        _persist_run_outcome(
            conn, run_id=run_id, status="FAILED", counts=counts, error=error
        )
        finish_ingestion_run(conn, run_id, "FAILED", error=error)
        return {
            "run_id": run_id,
            "status": "FAILED",
            "error": "Corporate-action provider request failed.",
            **counts,
        }
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except duckdb.Error:
            pass
        error = {"stage": "corporate_actions", "type": type(exc).__name__}
        _persist_run_outcome(
            conn, run_id=run_id, status="FAILED", counts=counts, error=error
        )
        finish_ingestion_run(conn, run_id, "FAILED", error=error)
        raise
    finally:
        if owned:
            client.close()


def _persist_run_outcome(
    conn: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    status: str,
    counts: Mapping[str, int],
    error: Mapping[str, Any] | None = None,
) -> None:
    requested_count = 1
    success_count = 1 if status in {"COMPLETE", "PARTIAL"} else 0
    empty_count = 1 if status == "EMPTY" else 0
    failed_count = 1 if status in {"FAILED", "UNSUPPORTED"} else 0
    invalid_count = int(counts.get("quarantined", 0)) + int(counts.get("conflicts", 0))
    conn.execute(
        """
        UPDATE ingestion_run
        SET requested_count = ?, success_count = ?, empty_count = ?,
            failed_count = ?, invalid_count = ?, diagnostics_json = ?,
            terminal_reason = ?, error_json = COALESCE(?, error_json)
        WHERE ingestion_run_id = ?
        """,
        [
            requested_count,
            success_count,
            empty_count,
            failed_count,
            invalid_count,
            json.dumps({"counts": dict(counts)}, sort_keys=True),
            status,
            json.dumps(dict(error), sort_keys=True) if error else None,
            run_id,
        ],
    )


def corporate_action_status(
    conn: duckdb.DuckDBPyConnection,
    *,
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.strip().upper())
    if start:
        clauses.append(
            "COALESCE(ex_date, effective_date, record_date, announced_at) >= ?"
        )
        params.append(start)
    if end:
        clauses.append(
            "COALESCE(ex_date, effective_date, record_date, announced_at) <= ?"
        )
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT canonical_status, COUNT(*)
        FROM corporate_action
        {where}
        GROUP BY canonical_status
        """,
        params,
    ).fetchall()
    status_counts = {str(status): int(count) for status, count in rows}
    quarantine_clauses: list[str] = []
    quarantine_params: list[Any] = []
    if symbol:
        quarantine_clauses.append("symbol = ?")
        quarantine_params.append(symbol.strip().upper())
    quarantine_where = (
        f"WHERE {' AND '.join(quarantine_clauses)}" if quarantine_clauses else ""
    )
    quarantined = conn.execute(
        f"SELECT COUNT(*) FROM corporate_action_quarantine {quarantine_where}",
        quarantine_params,
    ).fetchone()[0]
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM corporate_action_affected_range WHERE resolved_at IS NULL"
        + (" AND symbol = ?" if symbol else ""),
        [symbol.strip().upper()] if symbol else [],
    ).fetchone()[0]
    latest = conn.execute(
        """
        SELECT ingestion_run_id, status, started_at, finished_at
        FROM ingestion_run
        WHERE source_endpoint = '/v1/reference/corporate-actions'
          AND (? IS NULL OR universe = ?)
        ORDER BY started_at DESC
        LIMIT 1
        """,
        [
            symbol.strip().upper() if symbol else None,
            symbol.strip().upper() if symbol else None,
        ],
    ).fetchone()
    return {
        "symbol": symbol.strip().upper() if symbol else None,
        "canonical_status_counts": status_counts,
        "quarantined": int(quarantined),
        "unresolved_affected_ranges": int(unresolved),
        "latest_run": (
            {
                "run_id": latest[0],
                "status": latest[1],
                "started_at": str(latest[2]),
                "finished_at": str(latest[3]) if latest[3] else None,
            }
            if latest
            else None
        ),
    }
