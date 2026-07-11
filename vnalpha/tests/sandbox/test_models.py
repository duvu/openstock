from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError


def test_parse_job_preserves_immutable_safe_request_values() -> None:
    from vnalpha.sandbox.models import (
        SandboxJobId,
        SandboxJobRequest,
        SandboxRunId,
    )

    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate candidate signal",
            "code": "result = 1",
            "correlation_id": "research-42",
            "resource_limits": {
                "cpu_millis": 500,
                "memory_mb": 128,
                "timeout_seconds": 10,
            },
            "network_enabled": False,
            "approved_input_paths": ("inputs/candidate.json",),
        }
    )

    job = request.into_job(
        job_id=SandboxJobId("job-001"), run_id=SandboxRunId("run-001")
    )

    assert job.job_id == SandboxJobId("job-001")
    assert job.network_enabled is False
    assert job.approved_input_paths == ("inputs/candidate.json",)


def test_parse_job_rejects_enabled_network_and_unsafe_input_paths() -> None:
    from vnalpha.sandbox.models import SandboxJobRequest

    with pytest.raises(ValidationError):
        _ = SandboxJobRequest.model_validate(
            {
                "purpose": "evaluate",
                "code": "result = 1",
                "correlation_id": "research-42",
                "resource_limits": {
                    "cpu_millis": 500,
                    "memory_mb": 128,
                    "timeout_seconds": 10,
                },
                "network_enabled": True,
                "approved_input_paths": ("../secrets.txt",),
            }
        )


def test_parsed_job_and_request_are_immutable_and_reject_lower_limits() -> None:
    from vnalpha.sandbox.models import (
        SandboxJobId,
        SandboxJobRequest,
        SandboxRunId,
    )

    request = SandboxJobRequest.model_validate(
        {
            "purpose": "evaluate",
            "code": "result = 1",
            "correlation_id": "research-42",
            "resource_limits": {
                "cpu_millis": 1,
                "memory_mb": 16,
                "timeout_seconds": 1,
            },
        }
    )
    job = request.into_job(
        job_id=SandboxJobId("job-001"), run_id=SandboxRunId("run-001")
    )

    with pytest.raises(ValidationError):
        request.__setattr__("purpose", "changed")
    with pytest.raises(FrozenInstanceError):
        job.__setattr__("purpose", "changed")
    with pytest.raises(ValidationError):
        _ = SandboxJobRequest.model_validate(
            {
                "purpose": "evaluate",
                "code": "result = 1",
                "correlation_id": "research-42",
                "resource_limits": {
                    "cpu_millis": 0,
                    "memory_mb": 16,
                    "timeout_seconds": 1,
                },
            }
        )
