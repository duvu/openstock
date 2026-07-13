from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vnalpha.sandbox.approval import SandboxApproval, SandboxApprovalRepository
from vnalpha.sandbox.models import SandboxCorrelationId, SandboxJobId
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


def _approval() -> SandboxApproval:
    return SandboxApproval.create(
        job_id=SandboxJobId("job-001"),
        plan_digest="a" * 64,
        code_digest="b" * 64,
        input_references=("inputs/prices.csv",),
        correlation_id=SandboxCorrelationId("correlation-001"),
        approver="user",
        approved_at=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )


def test_persists_immutable_approval_bound_to_exact_job_material() -> None:
    # Given
    approval = _approval()
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxApprovalRepository(conn)

        # When
        repository.create(approval)

        # Then
        persisted = repository.get(approval.approval_id)
        assert persisted == approval
        assert persisted is not None
        assert persisted.input_references_digest == approval.input_references_digest


def test_rejects_duplicate_approval_id_without_overwriting_evidence() -> None:
    # Given
    approval = _approval()
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxApprovalRepository(conn)
        repository.create(approval)

        # When / Then
        with pytest.raises(ValueError, match="already exists"):
            repository.create(approval)
        assert repository.get(approval.approval_id) == approval


def test_lists_approvals_for_job_newest_first() -> None:
    approval_one = SandboxApproval.create(
        job_id=SandboxJobId("job-001"),
        plan_digest="a" * 64,
        code_digest="b" * 64,
        input_references=("inputs/prices.csv",),
        correlation_id=SandboxCorrelationId("correlation-001"),
        approver="user",
        approved_at=datetime(2026, 7, 12, 10, tzinfo=timezone.utc),
    )
    approval_two = SandboxApproval.create(
        job_id=SandboxJobId("job-001"),
        plan_digest="a" * 64,
        code_digest="b" * 64,
        input_references=("inputs/prices.csv",),
        correlation_id=SandboxCorrelationId("correlation-001"),
        approver="ops",
        approved_at=datetime(2026, 7, 12, 11, tzinfo=timezone.utc),
    )

    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        repository = SandboxApprovalRepository(conn)
        repository.create(approval_one)
        repository.create(approval_two)

        listed = repository.list_for_job(SandboxJobId("job-001"))
        assert [row.approval_id for row in listed] == [
            approval_two.approval_id,
            approval_one.approval_id,
        ]
