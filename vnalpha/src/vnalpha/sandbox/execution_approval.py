from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb

from vnalpha.assistant.models import PreparedAssistantTurn
from vnalpha.sandbox.approval import SandboxApproval, SandboxApprovalRepository
from vnalpha.sandbox.execution_errors import SandboxExecutionError
from vnalpha.sandbox.models import SandboxJob


@dataclass(frozen=True, slots=True)
class SandboxApprovalContext:
    approver: str
    approved_at: datetime | None


def create_bound_approval(
    conn: duckdb.DuckDBPyConnection,
    prepared: PreparedAssistantTurn,
    job: SandboxJob,
    context: SandboxApprovalContext,
) -> SandboxApproval:
    approval = SandboxApproval.create(
        job_id=job.job_id,
        plan_digest=prepared.plan_hash,
        code_digest=job.code_digest,
        input_references=tuple(job.filesystem_policy.approved_read_paths),
        correlation_id=job.correlation_id,
        approver=context.approver,
        approved_at=context.approved_at or datetime.now(UTC),
    )
    SandboxApprovalRepository(conn).create(approval)
    return approval


def require_bound_approval(
    conn: duckdb.DuckDBPyConnection,
    prepared: PreparedAssistantTurn,
    job: SandboxJob,
) -> SandboxApproval:
    for approval in SandboxApprovalRepository(conn).list_for_job(job.job_id):
        if approval.plan_digest != prepared.plan_hash:
            continue
        if approval.code_digest != job.code_digest:
            continue
        if approval.correlation_id != job.correlation_id:
            continue
        if approval.input_references != tuple(
            job.filesystem_policy.approved_read_paths
        ):
            continue
        return approval
    raise SandboxExecutionError(
        "sandbox execution requires explicit approval before running"
    )
