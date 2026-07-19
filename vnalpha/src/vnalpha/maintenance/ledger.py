"""Maintenance run and stage ledger persistence for issue #252."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.maintenance.models import DailyMaintenanceResult, MaintenanceStageResult

if TYPE_CHECKING:
    import duckdb


def persist_maintenance_run(
    conn: duckdb.DuckDBPyConnection,
    result: DailyMaintenanceResult,
    *,
    started_at: datetime,
    completed_at: datetime,
    software_version: str,
    calendar_version: str | None = None,
) -> str:
    """Persist one complete maintenance run and its stages to the ledger.

    Returns:
        run_id: The generated run identifier.
    """
    run_id = f"maint_{uuid4().hex[:12]}"
    duration_seconds = (completed_at - started_at).total_seconds()

    # Insert maintenance_run record
    conn.execute(
        """
        INSERT INTO maintenance_run (
            run_id, correlation_id, requested_date, resolved_date, status,
            requested_symbol_count, successful_symbol_count, failed_symbol_count,
            started_at, completed_at, duration_seconds,
            software_version, calendar_version, mutated, diagnostics_refs
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            result.correlation_id,
            result.requested_date,
            result.resolved_date,
            result.status.value,
            len(result.requested_symbols),
            len(result.successful_symbols),
            len(result.failed_symbols),
            started_at,
            completed_at,
            duration_seconds,
            software_version,
            calendar_version,
            result.mutated,
            json.dumps(list(result.diagnostics_refs)),
        ],
    )

    # Insert maintenance_stage_run records
    for order, stage in enumerate(result.stages, start=1):
        _persist_stage_run(conn, run_id, stage, order)

    conn.commit()
    return run_id


def _persist_stage_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    stage: MaintenanceStageResult,
    stage_order: int,
) -> None:
    """Persist one stage result."""
    stage_run_id = f"{run_id}_stage_{stage_order:02d}"

    conn.execute(
        """
        INSERT INTO maintenance_stage_run (
            stage_run_id, run_id, stage_name, stage_order, status,
            counts, failures, warnings, diagnostics_refs, remediation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            stage_run_id,
            run_id,
            stage.name,
            stage_order,
            stage.status.value,
            json.dumps(stage.counts),
            json.dumps(list(stage.failures)),
            json.dumps(list(stage.warnings)),
            json.dumps(list(stage.diagnostics_refs)),
            json.dumps(list(stage.remediation)),
        ],
    )


def get_latest_maintenance_run(
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, object] | None:
    """Return the latest maintenance run record or None."""
    row = conn.execute(
        """
        SELECT
            run_id, correlation_id, requested_date, resolved_date, status,
            requested_symbol_count, successful_symbol_count, failed_symbol_count,
            started_at, completed_at, duration_seconds,
            software_version, calendar_version, mutated, diagnostics_refs
        FROM maintenance_run
        ORDER BY completed_at DESC
        LIMIT 1
        """
    ).fetchone()

    if not row:
        return None

    return {
        "run_id": row[0],
        "correlation_id": row[1],
        "requested_date": row[2],
        "resolved_date": row[3],
        "status": row[4],
        "requested_symbol_count": row[5],
        "successful_symbol_count": row[6],
        "failed_symbol_count": row[7],
        "started_at": row[8].isoformat() if row[8] else None,
        "completed_at": row[9].isoformat() if row[9] else None,
        "duration_seconds": row[10],
        "software_version": row[11],
        "calendar_version": row[12],
        "mutated": row[13],
        "diagnostics_refs": json.loads(row[14]) if row[14] else [],
    }


def get_failed_maintenance_stages(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Return recent failed maintenance stages."""
    rows = conn.execute(
        """
        SELECT
            s.stage_run_id, s.run_id, s.stage_name, s.status,
            s.failures, s.warnings, s.diagnostics_refs,
            r.completed_at, r.resolved_date
        FROM maintenance_stage_run s
        JOIN maintenance_run r ON s.run_id = r.run_id
        WHERE s.status IN ('FAILED', 'PARTIAL')
        ORDER BY r.completed_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "stage_run_id": row[0],
            "run_id": row[1],
            "stage_name": row[2],
            "status": row[3],
            "failures": json.loads(row[4]) if row[4] else [],
            "warnings": json.loads(row[5]) if row[5] else [],
            "diagnostics_refs": json.loads(row[6]) if row[6] else [],
            "completed_at": row[7].isoformat() if row[7] else None,
            "resolved_date": row[8],
        }
        for row in rows
    ]


def get_maintenance_run_stages(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
) -> list[dict[str, object]]:
    """Return all stages for a specific maintenance run."""
    rows = conn.execute(
        """
        SELECT
            stage_run_id, stage_name, stage_order, status,
            counts, failures, warnings, diagnostics_refs, remediation
        FROM maintenance_stage_run
        WHERE run_id = ?
        ORDER BY stage_order
        """,
        [run_id],
    ).fetchall()

    return [
        {
            "stage_run_id": row[0],
            "stage_name": row[1],
            "stage_order": row[2],
            "status": row[3],
            "counts": json.loads(row[4]) if row[4] else {},
            "failures": json.loads(row[5]) if row[5] else [],
            "warnings": json.loads(row[6]) if row[6] else [],
            "diagnostics_refs": json.loads(row[7]) if row[7] else [],
            "remediation": json.loads(row[8]) if row[8] else [],
        }
        for row in rows
    ]
