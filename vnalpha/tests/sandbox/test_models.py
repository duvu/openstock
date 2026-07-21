from __future__ import annotations


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
