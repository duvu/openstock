from __future__ import annotations

import json

from vnalpha.assistant.models import AssistantAnswer
from vnalpha.sandbox._output_validation_types import parse_result
from vnalpha.sandbox.execution_errors import SandboxExecutionError
from vnalpha.sandbox.models import SandboxJob, SandboxJobStatus
from vnalpha.sandbox.storage import SandboxArtifactStorage

_MAX_MANIFEST_BYTES = 262_144
_MAX_RESULT_BYTES = 1_048_576
_MAX_SUMMARY_BYTES = 262_144
_VALIDATED_ONLY_CAVEAT = (
    "Validated artifacts only; generated code, stdout, stderr, and "
    "unvalidated files were not used for the final answer."
)


def success_answer(
    job: SandboxJob,
    storage: SandboxArtifactStorage,
    step_id: str,
) -> AssistantAnswer:
    result = parse_result(
        storage.read_bounded_regular_file(
            "output/result.json", max_bytes=_MAX_RESULT_BYTES
        )
    )
    if result is None:
        raise SandboxExecutionError("validated sandbox result could not be parsed")
    _ = storage.read_bounded_regular_file(
        "output/summary.md", max_bytes=_MAX_SUMMARY_BYTES
    )
    manifest = json.loads(
        storage.read_bounded_regular_file(
            "manifest.json", max_bytes=_MAX_MANIFEST_BYTES
        )
    )
    return AssistantAnswer(
        summary=result.summary,
        basis=(
            f"Validated sandbox job {job.job_id} completed with "
            f"{len(manifest.get('entries', []))} persisted artifacts."
        ),
        risks_caveats="Research-only sandbox result. " + _VALIDATED_ONLY_CAVEAT,
        tool_trace_summary="Executed sandbox.run_research_code through the Docker sandbox.",
        grounded_source_refs=[
            f"tool:sandbox.run_research_code:{step_id}",
            str(job.job_id),
        ],
        research_metadata={
            "sandbox_job_id": str(job.job_id),
            "sandbox_run_id": str(job.run_id),
            "sandbox_correlation_id": str(job.correlation_id),
            "sandbox_manifest_path": f"logs/runs/{job.run_id}/sandbox/{job.job_id}/manifest.json",
        },
    )


def rejected_answer(job: SandboxJob) -> AssistantAnswer:
    return AssistantAnswer(
        summary=f"Sandbox job {job.job_id} was rejected before execution.",
        basis="The static sandbox guard rejected the retained generated code.",
        risks_caveats=_VALIDATED_ONLY_CAVEAT,
        tool_trace_summary="No validated sandbox result was produced.",
        research_metadata={
            "sandbox_job_id": str(job.job_id),
            "sandbox_status": SandboxJobStatus.REJECTED.value,
        },
    )


def failed_answer(job: SandboxJob, failure_reason: str) -> AssistantAnswer:
    return AssistantAnswer(
        summary=f"Sandbox job {job.job_id} failed: {failure_reason}.",
        basis="The Docker sandbox did not produce a validated result.",
        risks_caveats=_VALIDATED_ONLY_CAVEAT,
        tool_trace_summary="No validated sandbox result was produced.",
        research_metadata={
            "sandbox_job_id": str(job.job_id),
            "sandbox_status": SandboxJobStatus.FAILED.value,
        },
    )
