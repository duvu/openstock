"""Append-only approval evidence bound to immutable sandbox job material."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import duckdb

from vnalpha.sandbox.models import SandboxCorrelationId, SandboxJobId


@dataclass(frozen=True, slots=True)
class SandboxApproval:
    """The exact user approval required before generated code can execute."""

    approval_id: str
    job_id: SandboxJobId
    plan_digest: str
    code_digest: str
    input_references: tuple[str, ...]
    input_references_digest: str
    correlation_id: SandboxCorrelationId
    approver: str
    approved_at: datetime

    @classmethod
    def create(
        cls,
        *,
        job_id: SandboxJobId,
        plan_digest: str,
        code_digest: str,
        input_references: tuple[str, ...],
        correlation_id: SandboxCorrelationId,
        approver: str,
        approved_at: datetime,
    ) -> SandboxApproval:
        """Create a validated, immutable approval record."""
        _validate_digest("plan_digest", plan_digest)
        _validate_digest("code_digest", code_digest)
        if (
            not job_id
            or not correlation_id
            or not approver.strip()
            or approved_at.tzinfo is None
        ):
            raise ValueError(
                "sandbox approval requires job, correlation, approver, and timestamp"
            )
        if any(not value or "\x00" in value for value in input_references):
            raise ValueError(
                "sandbox approval input references must be non-empty strings"
            )
        references_json = _references_json(input_references)
        return cls(
            approval_id=uuid4().hex,
            job_id=job_id,
            plan_digest=plan_digest,
            code_digest=code_digest,
            input_references=input_references,
            input_references_digest=hashlib.sha256(
                references_json.encode()
            ).hexdigest(),
            correlation_id=correlation_id,
            approver=approver.strip(),
            approved_at=approved_at,
        )


class SandboxApprovalRepository:
    """Persist immutable sandbox approval evidence through DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def create(self, approval: SandboxApproval) -> None:
        """Append approval evidence, refusing to overwrite existing records."""
        try:
            self._conn.execute(
                """
                INSERT INTO sandbox_approval (
                    approval_id, job_id, plan_digest, code_digest,
                    input_references_json, input_references_digest,
                    correlation_id, approver, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    approval.approval_id,
                    approval.job_id,
                    approval.plan_digest,
                    approval.code_digest,
                    _references_json(approval.input_references),
                    approval.input_references_digest,
                    approval.correlation_id,
                    approval.approver,
                    approval.approved_at,
                ],
            )
        except duckdb.ConstraintException as exc:
            raise ValueError("sandbox approval already exists") from exc

    def get(self, approval_id: str) -> SandboxApproval | None:
        """Load one approval record without any mutable update operation."""
        row = self._conn.execute(
            """
            SELECT approval_id, job_id, plan_digest, code_digest,
                   input_references_json, input_references_digest,
                   correlation_id, approver, approved_at
            FROM sandbox_approval WHERE approval_id = ?
            """,
            [approval_id],
        ).fetchone()
        if row is None:
            return None
        references = tuple(json.loads(row[4]))
        return SandboxApproval(
            approval_id=row[0],
            job_id=SandboxJobId(row[1]),
            plan_digest=row[2],
            code_digest=row[3],
            input_references=references,
            input_references_digest=row[5],
            correlation_id=SandboxCorrelationId(row[6]),
            approver=row[7],
            approved_at=row[8],
        )


def _validate_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"sandbox approval {name} must be a SHA-256 hex digest")


def _references_json(references: tuple[str, ...]) -> str:
    return json.dumps(references, separators=(",", ":"), ensure_ascii=True)
