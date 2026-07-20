"""Maintenance run and stage ledger persistence for issue #252."""

from __future__ import annotations

import json
from datetime import date as DateType
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from vnalpha.ingestion.trading_calendar import (
    CalendarCoverageError,
    SessionRange,
    VietnamSessionCalendar,
)
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
    package_version: str | None = None,
    source_commit: str | None = None,
    tree_state: str | None = None,
    calendar_version: str | None = None,
    source_policy: dict[str, object] | None = None,
) -> str:
    """Persist one complete maintenance invocation and its ordered stages."""
    run_id = f"maint_{uuid4().hex[:12]}"
    duration_seconds = (completed_at - started_at).total_seconds()

    conn.execute(
        """
        INSERT INTO maintenance_run (
            run_id, correlation_id, requested_date, resolved_date, status,
            requested_symbol_count, successful_symbol_count, failed_symbol_count,
            started_at, completed_at, duration_seconds,
            software_version, package_version, source_commit, tree_state,
            calendar_version, mutated, diagnostics_refs, source_policy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            package_version,
            source_commit,
            tree_state,
            calendar_version,
            result.mutated,
            json.dumps(list(result.diagnostics_refs)),
            json.dumps(source_policy) if source_policy is not None else None,
        ],
    )

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
    row = conn.execute(
        """
        SELECT
            run_id, correlation_id, requested_date, resolved_date, status,
            requested_symbol_count, successful_symbol_count, failed_symbol_count,
            started_at, completed_at, duration_seconds,
            software_version, package_version, source_commit, tree_state,
            calendar_version, mutated, diagnostics_refs, source_policy
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
        "package_version": row[12],
        "source_commit": row[13],
        "tree_state": row[14],
        "calendar_version": row[15],
        "mutated": row[16],
        "diagnostics_refs": json.loads(row[17]) if row[17] else [],
        "source_policy": json.loads(row[18]) if row[18] else None,
    }


def get_failed_maintenance_stages(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 10,
) -> list[dict[str, object]]:
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


def collect_operational_proof(
    conn: duckdb.DuckDBPyConnection,
    *,
    required_sessions: int = 10,
    required_rerun_dates: int = 2,
    calendar: VietnamSessionCalendar | None = None,
) -> dict[str, object]:
    """Validate persisted operational evidence without fabricating live runs."""
    if required_sessions < 1:
        raise ValueError("required_sessions must be positive")
    if required_rerun_dates < 0:
        raise ValueError("required_rerun_dates must be non-negative")

    rows = conn.execute(
        """
        WITH ranked AS (
            SELECT run_id, resolved_date, status, correlation_id,
                   requested_symbol_count, successful_symbol_count,
                   failed_symbol_count, software_version, package_version,
                   source_commit, tree_state, calendar_version, duration_seconds,
                   completed_at, source_policy,
                   ROW_NUMBER() OVER (
                       PARTITION BY resolved_date ORDER BY completed_at DESC
                   ) AS rn,
                   COUNT(*) OVER (PARTITION BY resolved_date) AS invocations
            FROM maintenance_run
            WHERE status <> 'NOOP'
        )
        SELECT run_id, resolved_date, status, correlation_id,
               requested_symbol_count, successful_symbol_count,
               failed_symbol_count, software_version, package_version,
               source_commit, tree_state, calendar_version, duration_seconds,
               completed_at, source_policy, invocations
        FROM ranked
        WHERE rn = 1
        ORDER BY resolved_date DESC
        LIMIT ?
        """,
        [required_sessions],
    ).fetchall()

    sessions = [
        {
            "run_id": row[0],
            "resolved_date": str(row[1]),
            "status": row[2],
            "correlation_id": row[3],
            "requested_symbol_count": row[4],
            "successful_symbol_count": row[5],
            "failed_symbol_count": row[6],
            "software_version": row[7],
            "package_version": row[8],
            "source_commit": row[9],
            "tree_state": row[10],
            "calendar_version": row[11],
            "duration_seconds": row[12],
            "completed_at": row[13].isoformat() if row[13] else None,
            "source_policy": json.loads(row[14]) if row[14] else None,
            "same_date_invocations": row[15],
        }
        for row in rows
    ]
    sessions.sort(key=lambda item: item["resolved_date"])

    proof_calendar = calendar or VietnamSessionCalendar()
    recorded_dates = [
        DateType.fromisoformat(str(item["resolved_date"])) for item in sessions
    ]
    expected_dates: list[DateType] = []
    calendar_error: str | None = None
    if recorded_dates:
        try:
            configured = proof_calendar.sessions(
                SessionRange(recorded_dates[0], recorded_dates[-1])
            )
            expected_dates = list(configured[-required_sessions:])
        except CalendarCoverageError as exc:
            calendar_error = str(exc)

    consecutive = (
        len(recorded_dates) >= required_sessions
        and recorded_dates[-required_sessions:] == expected_dates
        and len(expected_dates) == required_sessions
    )
    missing_dates = [
        value.isoformat() for value in expected_dates if value not in recorded_dates
    ]
    rerun_dates = [
        str(item["resolved_date"])
        for item in sessions
        if int(item["same_date_invocations"]) > 1
    ]
    identity_complete = all(
        item["package_version"] and item["source_commit"] and item["calendar_version"]
        for item in sessions
    )
    source_policy_complete = all(item["source_policy"] for item in sessions)
    has_required_sessions = (
        consecutive
        and len(rerun_dates) >= required_rerun_dates
        and identity_complete
        and source_policy_complete
    )

    return {
        "required_sessions": required_sessions,
        "required_rerun_dates": required_rerun_dates,
        "distinct_sessions_recorded": len(sessions),
        "consecutive_market_sessions": consecutive,
        "has_required_sessions": has_required_sessions,
        "session_dates": [value.isoformat() for value in recorded_dates],
        "expected_session_dates": [value.isoformat() for value in expected_dates],
        "missing_session_dates": missing_dates,
        "same_date_rerun_dates": rerun_dates,
        "identity_complete": identity_complete,
        "source_policy_complete": source_policy_complete,
        "calendar_error": calendar_error,
        "sessions": sessions,
    }


__all__ = [
    "collect_operational_proof",
    "get_failed_maintenance_stages",
    "get_latest_maintenance_run",
    "get_maintenance_run_stages",
    "persist_maintenance_run",
]
