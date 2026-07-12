from __future__ import annotations

from vnalpha.closed_loop.models import LifecycleState, RepairBundle


def test_lifecycle_has_canonical_closed_loop_states() -> None:
    states = {state.value for state in LifecycleState}

    assert states == {
        "RUN",
        "OBSERVE",
        "PACKAGE",
        "AI_FIX",
        "VALIDATE",
        "PROMOTE_READY",
        "PROMOTED",
        "REJECTED",
        "ROLLED_BACK",
        "FAILED",
    }


def test_repair_bundle_requires_complete_diagnostic_context() -> None:
    bundle = RepairBundle(
        repair_id="repair-1",
        correlation_id="corr-1",
        failed_job_id="job-1",
        failed_session_id="session-1",
        user_request="build feature",
        plan_summary="sandbox research plan",
        generated_code="result = 1",
        static_guard_result={"allowed": True},
        stdout="stdout",
        stderr="stderr",
        error_trace="Traceback",
        input_dataset_references=("ohlcv:2026-07-10",),
        artifact_manifest={"artifact_id": "artifact-1"},
        output_state={"status": "FAILED"},
        validation_result={"status": "FAILED"},
        environment_summary={"python": "3.12"},
        redaction_status="redacted",
    )

    assert bundle.failed_session_id == "session-1"
    assert bundle.redaction_status == "redacted"
