from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

import duckdb

from vnalpha.scoring.policy import PolicyLifecycleStatus
from vnalpha.scoring.policy_decision import (
    DEFAULT_SCORING_POLICY_CONTEXT,
    ScoringPolicyDecision,
)

_DECISION_COLUMNS = (
    "decision_id",
    "scoring_policy_id",
    "scoring_policy_version",
    "scoring_policy_hash",
    "decision_status",
    "effective_date",
    "decision_cutoff_date",
    "reviewer",
    "rationale",
    "evidence_json",
    "limitations_json",
    "reviewed_at",
    "created_at",
)


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchone()
        is not None
    )


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(
        value if value is not None else [], sort_keys=True, separators=(",", ":")
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_decision(row: tuple[Any, ...]) -> ScoringPolicyDecision:
    return ScoringPolicyDecision.from_row(
        dict(zip(_DECISION_COLUMNS, row, strict=False))
    )


def get_scoring_policy_decision(
    conn: duckdb.DuckDBPyConnection,
    decision_id: str,
) -> ScoringPolicyDecision | None:
    row = conn.execute(
        """
        SELECT decision_id, scoring_policy_id, scoring_policy_version, scoring_policy_hash,
               decision_status, effective_date, decision_cutoff_date, reviewer, rationale,
               evidence_json, limitations_json, reviewed_at, created_at
        FROM scoring_policy_decision
        WHERE decision_id = ?
        """,
        [decision_id],
    ).fetchone()
    return None if row is None else _row_to_decision(row)


def get_active_scoring_policy_decision(
    conn: duckdb.DuckDBPyConnection,
    policy_context: str = DEFAULT_SCORING_POLICY_CONTEXT,
) -> ScoringPolicyDecision | None:
    row = conn.execute(
        """
        SELECT d.decision_id, d.scoring_policy_id, d.scoring_policy_version,
               d.scoring_policy_hash, d.decision_status, d.effective_date,
               d.decision_cutoff_date, d.reviewer, d.rationale,
               d.evidence_json, d.limitations_json, d.reviewed_at, d.created_at
        FROM scoring_policy_active_pointer p
        JOIN scoring_policy_decision d
          ON d.decision_id = p.decision_id
        WHERE p.policy_context = ?
        """,
        [policy_context],
    ).fetchone()
    return None if row is None else _row_to_decision(row)


def get_previous_scoring_policy_decision(
    conn: duckdb.DuckDBPyConnection,
    policy_context: str = DEFAULT_SCORING_POLICY_CONTEXT,
) -> ScoringPolicyDecision | None:
    current = conn.execute(
        """
        SELECT decision_id, assigned_by, assigned_at
        FROM scoring_policy_active_pointer
        WHERE policy_context = ?
        """,
        [policy_context],
    ).fetchone()
    if current is None:
        return None

    current_decision_id, _, current_assigned_at = current
    if not _table_exists(conn, "scoring_policy_active_pointer_audit"):
        row = conn.execute(
            """
            SELECT decision_id
            FROM scoring_policy_decision
            WHERE decision_id != ?
            ORDER BY reviewed_at DESC
            LIMIT 1
            """,
            [current_decision_id],
        ).fetchone()
        if row is None:
            return None
        return get_scoring_policy_decision(conn, str(row[0]))

    row = conn.execute(
        """
        SELECT decision_id
        FROM scoring_policy_active_pointer_audit
        WHERE policy_context = ?
          AND assigned_at <= ?
          AND decision_id != ?
        ORDER BY assigned_at DESC
        LIMIT 1
        """,
        [policy_context, current_assigned_at, current_decision_id],
    ).fetchone()
    if row is None:
        return None
    return get_scoring_policy_decision(conn, str(row[0]))


def set_active_scoring_policy_decision_pointer(
    conn: duckdb.DuckDBPyConnection,
    decision_id: str,
    *,
    policy_context: str = DEFAULT_SCORING_POLICY_CONTEXT,
    assigned_by: str | None = None,
) -> None:
    if (
        conn.execute(
            "SELECT 1 FROM scoring_policy_decision WHERE decision_id = ?",
            [decision_id],
        ).fetchone()
        is None
    ):
        return

    if _table_exists(conn, "scoring_policy_active_pointer_audit"):
        conn.execute(
            """
            INSERT INTO scoring_policy_active_pointer_audit (
                policy_context,
                decision_id,
                assigned_by,
                assigned_at
            )
            SELECT
                policy_context,
                decision_id,
                assigned_by,
                assigned_at
            FROM scoring_policy_active_pointer
            WHERE policy_context = ?
              AND decision_id != ?
            """,
            [policy_context, decision_id],
        )

    updated = conn.execute(
        """
        UPDATE scoring_policy_active_pointer
        SET decision_id = ?,
            assigned_by = ?,
            assigned_at = CURRENT_TIMESTAMP
        WHERE policy_context = ?
        """,
        [decision_id, assigned_by, policy_context],
    ).rowcount
    if updated == 0:
        conn.execute(
            """
            INSERT INTO scoring_policy_active_pointer (
                policy_context,
                decision_id,
                assigned_by
            )
            VALUES (?, ?, ?)
            """,
            [policy_context, decision_id, assigned_by],
        )


def list_scoring_policy_decisions(
    conn: duckdb.DuckDBPyConnection,
    *,
    policy_id: str | None = None,
    policy_version: str | None = None,
    status: PolicyLifecycleStatus | None = None,
) -> list[ScoringPolicyDecision]:
    clauses: list[str] = []
    params: list[Any] = []
    if policy_id is not None:
        clauses.append("scoring_policy_id = ?")
        params.append(policy_id)
    if policy_version is not None:
        clauses.append("scoring_policy_version = ?")
        params.append(policy_version)
    if status is not None:
        clauses.append("decision_status = ?")
        params.append(status.value)

    query = """
        SELECT decision_id, scoring_policy_id, scoring_policy_version,
               scoring_policy_hash, decision_status, effective_date,
               decision_cutoff_date, reviewer, rationale,
               evidence_json, limitations_json, reviewed_at, created_at
        FROM scoring_policy_decision
    """
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY effective_date DESC, reviewed_at DESC"

    rows = conn.execute(query, params).fetchall()
    return [_row_to_decision(row) for row in rows]


def create_scoring_policy_decision(
    conn: duckdb.DuckDBPyConnection,
    *,
    policy_id: str,
    policy_version: str,
    policy_hash: str,
    status: PolicyLifecycleStatus,
    effective_date: date,
    reviewer: str,
    rationale: str,
    evidence_json: str | Mapping[str, Any] | list[Any] = "[]",
    limitations_json: str | Mapping[str, Any] | list[Any] = "[]",
    decision_cutoff_date: date | None = None,
    reviewed_at: datetime | None = None,
    decision_id: str | None = None,
) -> str:
    resolved_id = decision_id or str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO scoring_policy_decision (
            decision_id,
            scoring_policy_id,
            scoring_policy_version,
            scoring_policy_hash,
            decision_status,
            effective_date,
            decision_cutoff_date,
            reviewer,
            rationale,
            evidence_json,
            limitations_json,
            reviewed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            resolved_id,
            policy_id,
            policy_version,
            policy_hash,
            status.value,
            effective_date,
            decision_cutoff_date,
            reviewer,
            rationale,
            _json_text(evidence_json),
            _json_text(limitations_json),
            reviewed_at or _now_iso(),
        ],
    )
    return resolved_id


__all__ = [
    "create_scoring_policy_decision",
    "get_active_scoring_policy_decision",
    "get_previous_scoring_policy_decision",
    "get_scoring_policy_decision",
    "list_scoring_policy_decisions",
    "set_active_scoring_policy_decision_pointer",
]
