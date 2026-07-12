from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Final
from uuid import uuid4

from vnalpha.assistant.models import (
    AssistantAnswer,
    AssistantPlan,
    PreparedAssistantTurn,
)
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import (
    RunContext,
    get_correlation_id,
    get_run_context,
    init_run_context,
    set_correlation_id,
)
from vnalpha.sandbox._output_validation_types import parse_result
from vnalpha.sandbox.approval import SandboxApproval, SandboxApprovalRepository
from vnalpha.sandbox.artifact_writer import SandboxArtifactWriter
from vnalpha.sandbox.docker_orchestration import (
    SandboxDockerOrchestrationRequest,
    SandboxDockerOrchestrator,
)
from vnalpha.sandbox.docker_runner import (
    DockerFailureCode,
    DockerImageReference,
    DockerRunner,
    SubprocessDockerCommand,
    parse_docker_image_reference,
)
from vnalpha.sandbox.models import (
    SandboxCorrelationId,
    SandboxJob,
    SandboxJobId,
    SandboxJobRequest,
    SandboxJobStatus,
    SandboxResourceLimits,
    SandboxRunId,
)
from vnalpha.sandbox.output_validation import SandboxOutputValidator
from vnalpha.sandbox.repository import SandboxJobRecord, SandboxJobRepository
from vnalpha.sandbox.static_guard import SandboxStaticGuard
from vnalpha.sandbox.storage import SandboxArtifactStorage

_DEFAULT_IMAGE: Final = f"registry.example/openstock/vnalpha-sandbox@sha256:{'a' * 64}"
_DEFAULT_LIMITS: Final = SandboxResourceLimits(
    cpu_millis=500,
    memory_mb=256,
    timeout_seconds=30,
)
_MAX_REQUEST_BYTES: Final = 32_768
_MAX_CODE_BYTES: Final = 65_536
_MAX_INPUT_REFERENCE_BYTES: Final = 16_384
_MAX_MANIFEST_BYTES: Final = 262_144
_MAX_RESULT_BYTES: Final = 1_048_576
_MAX_SUMMARY_BYTES: Final = 262_144
_DEFAULT_APPROVER: Final = "user"
_VALIDATED_ONLY_CAVEAT: Final = (
    "Validated artifacts only; generated code, stdout, stderr, and "
    "unvalidated files were not used for the final answer."
)


@dataclass(frozen=True, slots=True)
class SandboxGeneratedProgram:
    code: str
    summary: str
    input_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SandboxPreview:
    job: SandboxJob
    code_summary: str
    image: DockerImageReference

    @property
    def arguments(self) -> dict[str, object]:
        return {
            "purpose": self.job.purpose,
            "job_id": str(self.job.job_id),
            "run_id": str(self.job.run_id),
            "correlation_id": str(self.job.correlation_id),
            "code_summary": self.code_summary,
            "code_digest": self.job.code_digest,
            "input_references": list(self.job.filesystem_policy.approved_read_paths),
            "resource_limits": {
                "cpu_millis": self.job.resource_limits.cpu_millis,
                "memory_mb": self.job.resource_limits.memory_mb,
                "timeout_seconds": self.job.resource_limits.timeout_seconds,
            },
            "image": str(self.image),
            "image_digest": str(self.image).split("@", 1)[1],
        }


class SandboxExecutionService:
    def __init__(
        self,
        conn,
        *,
        surface: str,
        run_context: RunContext | None = None,
        image: DockerImageReference | str | None = None,
        docker_runner=None,
        code_generator: Callable[[str], SandboxGeneratedProgram] | None = None,
    ) -> None:
        self._conn = conn
        self._surface = surface
        self._run_context = run_context
        raw_image = str(
            image or os.environ.get("VNALPHA_SANDBOX_IMAGE", _DEFAULT_IMAGE)
        )
        self._image = parse_docker_image_reference(raw_image)
        self._docker_runner = docker_runner
        self._code_generator = code_generator or self._default_code_generator

    def materialize_assistant_plan(self, plan: AssistantPlan) -> AssistantPlan:
        if len(plan.steps) != 1:
            return plan
        step = plan.steps[0]
        if step.tool_name != "sandbox.run_research_code":
            return plan
        if "job_id" in step.arguments:
            return plan
        purpose = str(
            step.arguments.get("purpose", "offline research calculation")
        ).strip()
        preview = self.prepare_job(purpose)
        materialized_step = replace(step, arguments=preview.arguments)
        return replace(plan, steps=[materialized_step])

    def prepare_job(self, purpose: str) -> SandboxPreview:
        correlation_id = self._ensure_correlation_id()
        run_context = self._resolve_run_context()
        program = self._code_generator(purpose)
        job_id = SandboxJobId(f"job-{uuid4().hex}")
        request = SandboxJobRequest.model_validate(
            {
                "purpose": purpose,
                "code": program.code,
                "correlation_id": str(correlation_id),
                "resource_limits": {
                    "cpu_millis": _DEFAULT_LIMITS.cpu_millis,
                    "memory_mb": _DEFAULT_LIMITS.memory_mb,
                    "timeout_seconds": _DEFAULT_LIMITS.timeout_seconds,
                },
                "approved_input_paths": tuple(program.input_references),
            }
        )
        job = request.into_job(job_id=job_id, run_id=SandboxRunId(run_context.run_id))
        SandboxJobRepository(self._conn).create(job)
        with SandboxArtifactStorage(run_context, job.job_id) as storage:
            writer = SandboxArtifactWriter(storage)
            writer.persist_request(job)
            self._persist_lifecycle_event(
                writer,
                job,
                event_type="SANDBOX_JOB_CREATED",
                status=SandboxJobStatus.QUEUED.value,
                summary="Sandbox job created and awaiting approval.",
                metadata={
                    "code_digest": job.code_digest,
                    "image_digest": str(self._image).split("@", 1)[1],
                    "cpu_millis": job.resource_limits.cpu_millis,
                    "memory_mb": job.resource_limits.memory_mb,
                    "timeout_seconds": job.resource_limits.timeout_seconds,
                    "input_reference_count": len(
                        job.filesystem_policy.approved_read_paths
                    ),
                    "network_enabled": job.network_enabled,
                },
            )
        return SandboxPreview(job=job, code_summary=program.summary, image=self._image)

    def execute_prepared_turn(self, prepared: PreparedAssistantTurn) -> AssistantAnswer:
        if len(prepared.plan.steps) != 1:
            raise ValueError("sandbox execution requires exactly one prepared step")
        step = prepared.plan.steps[0]
        if step.tool_name != "sandbox.run_research_code":
            raise ValueError("prepared plan is not a sandbox execution request")
        job = self._load_retained_job(step.arguments)
        self._require_approval(prepared=prepared, job=job)
        with SandboxArtifactStorage(
            self._run_context_for(job.run_id), job.job_id
        ) as storage:
            writer = SandboxArtifactWriter(storage)
            writer.persist_request(job)
            validator = SandboxOutputValidator(storage)
            guard = SandboxStaticGuard.evaluate(job.code)
            writer.persist_guard(guard)
            repository = SandboxJobRepository(self._conn)
            if not guard.allowed:
                repository.mark_rejected(
                    job.job_id, "sandbox static guard rejected generated code"
                )
                self._persist_lifecycle_event(
                    writer,
                    job,
                    event_type="SANDBOX_GUARD_REJECTED",
                    status=SandboxJobStatus.REJECTED.value,
                    summary="Sandbox job was rejected by the static guard.",
                    metadata={
                        "code_digest": guard.code_digest,
                        "rule_codes": sorted(
                            {violation.rule.value for violation in guard.violations}
                        ),
                        "violation_count": len(guard.violations),
                    },
                )
                self._persist_manifest(writer, validator, job)
                return self._rejected_answer(job)

            self._persist_lifecycle_event(
                writer,
                job,
                event_type="SANDBOX_JOB_STARTED",
                status=SandboxJobStatus.RUNNING.value,
                summary="Sandbox job execution started.",
                metadata={
                    "image_digest": str(self._image).split("@", 1)[1],
                    "runtime_kind": "docker",
                },
            )
            orchestrator = SandboxDockerOrchestrator(
                storage,
                writer,
                self._runner(),
                validator,
                repository,
            )
            result = orchestrator.execute(
                SandboxDockerOrchestrationRequest(
                    job=job, guard_result=guard, image=self._image
                )
            )
            if result.status.value == "succeeded":
                self._persist_lifecycle_event(
                    writer,
                    job,
                    event_type="SANDBOX_JOB_SUCCEEDED",
                    status=SandboxJobStatus.SUCCEEDED.value,
                    summary="Sandbox job completed successfully.",
                    metadata={
                        "image_digest": str(self._image).split("@", 1)[1],
                    },
                )
                self._persist_manifest(writer, validator, job)
                return self._success_answer(job, storage, step.step_id)

            failure_reason = self._failure_reason(result.failure_code)
            stored = repository.get(job.job_id)
            if result.status.value == "rejected":
                if stored is not None and stored.status is SandboxJobStatus.QUEUED:
                    repository.mark_rejected(job.job_id, failure_reason)
            elif stored is not None and stored.status is SandboxJobStatus.QUEUED:
                repository.mark_failed(job.job_id, failure_reason)
            self._persist_lifecycle_event(
                writer,
                job,
                event_type="SANDBOX_JOB_FAILED",
                status=(
                    repository.get(job.job_id) or stored or self._record_from_job(job)
                ).status.value,
                summary="Sandbox job did not produce a validated result.",
                metadata={
                    "failure_code": self._failure_code_value(result.failure_code),
                    "image_digest": str(self._image).split("@", 1)[1],
                },
            )
            self._persist_manifest(writer, validator, job)
            return self._failed_answer(job, failure_reason)

    def approve_prepared_turn(
        self,
        prepared: PreparedAssistantTurn,
        *,
        approver: str = _DEFAULT_APPROVER,
        approved_at: datetime | None = None,
    ) -> SandboxApproval:
        if len(prepared.plan.steps) != 1:
            raise ValueError("sandbox execution requires exactly one prepared step")
        step = prepared.plan.steps[0]
        if step.tool_name != "sandbox.run_research_code":
            raise ValueError("prepared plan is not a sandbox execution request")
        job = self._load_retained_job(step.arguments)
        approval = self._build_approval(
            prepared=prepared,
            job=job,
            approver=approver,
            approved_at=approved_at,
        )
        SandboxApprovalRepository(self._conn).create(approval)
        return approval

    def _require_approval(
        self,
        *,
        prepared: PreparedAssistantTurn,
        job: SandboxJob,
    ) -> SandboxApproval:
        approval = self._find_matching_approval(prepared=prepared, job=job)
        if approval is None:
            raise ValueError(
                "sandbox execution requires explicit approval before running"
            )
        return approval

    def _find_matching_approval(
        self,
        *,
        prepared: PreparedAssistantTurn,
        job: SandboxJob,
    ) -> SandboxApproval | None:
        repository = SandboxApprovalRepository(self._conn)
        for approval in repository.list_for_job(job.job_id):
            if approval.plan_digest != prepared.plan_hash:
                continue
            if approval.code_digest != job.code_digest:
                continue
            if approval.correlation_id != job.correlation_id:
                continue
            if approval.input_references != tuple(job.filesystem_policy.approved_read_paths):
                continue
            return approval
        return None

    def _build_approval(
        self,
        *,
        prepared: PreparedAssistantTurn,
        job: SandboxJob,
        approver: str,
        approved_at: datetime | None,
    ) -> SandboxApproval:
        return SandboxApproval.create(
            job_id=job.job_id,
            plan_digest=prepared.plan_hash,
            code_digest=job.code_digest,
            input_references=tuple(job.filesystem_policy.approved_read_paths),
            correlation_id=job.correlation_id,
            approver=approver,
            approved_at=approved_at or datetime.now(UTC),
        )

    def _runner(self):
        if self._docker_runner is not None:
            return self._docker_runner
        return DockerRunner(SubprocessDockerCommand(), platform.system())

    def _resolve_run_context(self) -> RunContext:
        if self._run_context is not None:
            return self._run_context
        current = get_run_context()
        if current is not None:
            self._run_context = current
            return current
        self._run_context = init_run_context(
            surface=self._surface,
            actor=self._surface,
            log_root=Path(os.environ.get("VNALPHA_LOG_ROOT", "/tmp/openstock-logs")),
        )
        return self._run_context

    def _run_context_for(self, run_id: SandboxRunId) -> RunContext:
        current = self._resolve_run_context()
        if current.run_id == str(run_id):
            return current
        return RunContext(
            run_id=str(run_id),
            surface=current.surface,
            actor=current.actor,
            log_root=current.log_root,
        )

    def _ensure_correlation_id(self) -> SandboxCorrelationId:
        correlation_id = get_correlation_id()
        if correlation_id in {"", "unset"}:
            correlation_id = set_correlation_id()
        return SandboxCorrelationId(correlation_id)

    def _load_retained_job(self, arguments: dict[str, object]) -> SandboxJob:
        job_id = SandboxJobId(str(arguments["job_id"]))
        run_id = SandboxRunId(str(arguments["run_id"]))
        storage_context = self._run_context_for(run_id)
        repository = SandboxJobRepository(self._conn)
        record = repository.get(job_id)
        if record is None:
            raise ValueError(f"sandbox job not found: {job_id}")
        with SandboxArtifactStorage(storage_context, job_id) as storage:
            request_payload = json.loads(
                storage.read_bounded_regular_file(
                    "request.json", max_bytes=_MAX_REQUEST_BYTES
                )
            )
            code = storage.read_bounded_regular_file(
                "generated_code.py", max_bytes=_MAX_CODE_BYTES
            ).decode("utf-8")
            references_payload = json.loads(
                storage.read_bounded_regular_file(
                    "inputs/references.json", max_bytes=_MAX_INPUT_REFERENCE_BYTES
                )
            )
        resource_limits = SandboxResourceLimits.model_validate(
            request_payload["resource_limits"]
        )
        job = SandboxJob(
            job_id=job_id,
            run_id=run_id,
            purpose=str(request_payload["purpose"]),
            code=code,
            correlation_id=SandboxCorrelationId(str(request_payload["correlation_id"])),
            resource_limits=resource_limits,
            network_enabled=bool(request_payload["network_enabled"]),
            filesystem_policy=record.filesystem_policy,
            output_schema=record.output_schema,
            status=record.status,
        )
        self._assert_binding(record, job, arguments, references_payload)
        return job

    def _assert_binding(
        self,
        record: SandboxJobRecord,
        job: SandboxJob,
        arguments: dict[str, object],
        references_payload: dict[str, object],
    ) -> None:
        expected_references = list(job.filesystem_policy.approved_read_paths)
        if record.code_digest != job.code_digest:
            raise ValueError("sandbox job digest mismatch")
        if str(arguments["code_digest"]) != job.code_digest:
            raise ValueError("sandbox approval binding changed")
        if str(arguments["purpose"]) != job.purpose:
            raise ValueError("sandbox purpose binding changed")
        if str(arguments["correlation_id"]) != str(job.correlation_id):
            raise ValueError("sandbox correlation binding changed")
        if list(arguments["input_references"]) != expected_references:
            raise ValueError("sandbox input binding changed")
        if references_payload.get("approved_read_paths", []) != expected_references:
            raise ValueError("sandbox retained input references changed")
        if arguments["resource_limits"] != {
            "cpu_millis": job.resource_limits.cpu_millis,
            "memory_mb": job.resource_limits.memory_mb,
            "timeout_seconds": job.resource_limits.timeout_seconds,
        }:
            raise ValueError("sandbox resource binding changed")
        if str(arguments["image"]) != str(self._image):
            self._image = parse_docker_image_reference(str(arguments["image"]))

    def _persist_manifest(
        self,
        writer: SandboxArtifactWriter,
        validator: SandboxOutputValidator,
        job: SandboxJob,
    ) -> None:
        validation = validator.validate(job.output_schema)
        writer.persist_validation_and_manifest(validation, job.output_schema)

    def _persist_lifecycle_event(
        self,
        writer: SandboxArtifactWriter,
        job: SandboxJob,
        *,
        event_type: str,
        status: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        payload = {
            "event_id": uuid4().hex,
            "created_at": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "job_id": str(job.job_id),
            "run_id": str(job.run_id),
            "correlation_id": str(job.correlation_id),
            "status": status,
            "summary": summary,
            "metadata": metadata,
        }
        writer.persist_lifecycle_event(payload)
        log_audit(
            event_type,
            summary,
            status=status,
            object_type="sandbox_job",
            object_id=str(job.job_id),
            extra={
                "job_id": str(job.job_id),
                "correlation_id": str(job.correlation_id),
                **metadata,
            },
            module="vnalpha.sandbox.execution_service",
            function="prepare_job"
            if event_type == "SANDBOX_JOB_CREATED"
            else "execute_prepared_turn",
        )

    def _success_answer(
        self,
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
            raise ValueError("validated sandbox result could not be parsed")
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
            risks_caveats=("Research-only sandbox result. " + _VALIDATED_ONLY_CAVEAT),
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

    def _rejected_answer(self, job: SandboxJob) -> AssistantAnswer:
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

    def _failed_answer(self, job: SandboxJob, failure_reason: str) -> AssistantAnswer:
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

    def _failure_reason(self, failure_code) -> str:
        if failure_code is None:
            return "sandbox execution did not produce a validated result"
        if failure_code in {
            DockerFailureCode.HOST_NOT_LINUX,
            DockerFailureCode.DOCKER_LAUNCH_FAILED,
            DockerFailureCode.DOCKER_NOT_FOUND,
            DockerFailureCode.DAEMON_UNAVAILABLE,
            DockerFailureCode.DAEMON_TIMEOUT,
            DockerFailureCode.SERVER_NOT_LINUX,
            DockerFailureCode.IMAGE_NOT_AVAILABLE,
            DockerFailureCode.IMAGE_PROBE_TIMEOUT,
        }:
            return "sandbox execution boundary rejected the job"
        if failure_code in {
            DockerFailureCode.RUNTIME_TIMEOUT,
            DockerFailureCode.RUNTIME_FAILED,
        }:
            return "sandbox runtime failed"
        return str(getattr(failure_code, "value", failure_code))

    def _failure_code_value(self, failure_code) -> str | None:
        if failure_code is None:
            return None
        return str(getattr(failure_code, "value", failure_code))

    def _record_from_job(self, job: SandboxJob) -> SandboxJobRecord:
        return SandboxJobRecord(
            job_id=job.job_id,
            run_id=job.run_id,
            correlation_id=job.correlation_id,
            purpose=job.purpose,
            code_digest=job.code_digest,
            status=job.status,
            filesystem_policy=job.filesystem_policy,
            output_schema=job.output_schema,
            result_summary=None,
            rejection_reason=None,
            failure_reason=None,
        )

    def _default_code_generator(self, purpose: str) -> SandboxGeneratedProgram:
        purpose_literal = json.dumps(purpose, ensure_ascii=False)
        code = "\n".join(
            [
                "import json",
                "",
                f"PURPOSE = {purpose_literal}",
                'SUMMARY = "Sandbox calculation completed for approved purpose."',
                "",
                'with open("output/result.json", "w", encoding="utf-8") as handle:',
                '    json.dump({"schema_version": 1, "summary": SUMMARY, "artifacts": [], "purpose": PURPOSE}, handle, ensure_ascii=0)',
                '    handle.write("\\n")',
                "",
                'with open("output/summary.md", "w", encoding="utf-8") as handle:',
                '    handle.write("# Sandbox Result\\n\\n")',
                '    handle.write("Validated output only.\\n")',
            ]
        )
        return SandboxGeneratedProgram(
            code=code,
            summary=(
                "Writes validated result.json and summary.md for the approved purpose "
                "using only offline JSON output."
            ),
        )
