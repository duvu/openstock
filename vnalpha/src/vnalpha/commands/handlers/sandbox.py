"""Read-only sandbox command surface with an explicit execution approval gate."""

from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.sandbox.layout import SandboxArtifactLayout
from vnalpha.sandbox.models import SandboxJobId
from vnalpha.sandbox.repository import SandboxJobRecord, SandboxJobRepository


def handle_sandbox(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    """Render sandbox metadata without starting generated-code execution."""
    if conn is None:
        return CommandResult(
            status="FAILED", title="/sandbox", summary="No database connection."
        )
    if not parsed.positional:
        raise CommandValidationError("Sandbox subcommand is required.")

    subcommand = parsed.positional[0].lower()
    if subcommand == "run":
        return _run_preview(parsed, conn=conn, surface=kwargs.get("surface", "cli"))

    repository = SandboxJobRepository(conn)
    if subcommand == "status":
        record = repository.get(_job_id_argument(parsed, "status"))
        return _status_result(record)
    if subcommand == "artifact":
        record = repository.get(_job_id_argument(parsed, "artifact"))
        return _artifact_result(record)
    if subcommand == "list":
        _validate_latest_query(parsed)
        records = repository.list()
        return _status_result(
            records[-1] if records else None, title="/sandbox list --latest"
        )
    raise CommandValidationError(
        "Unsupported /sandbox subcommand. Supported: run, status, artifact, list --latest."
    )


def _run_preview(parsed: ParsedCommand, *, conn, surface: str) -> CommandResult:
    if parsed.options or parsed.filters:
        raise CommandValidationError("/sandbox run accepts only a purpose.")
    purpose = " ".join(parsed.positional[1:]).strip()
    if not purpose:
        raise CommandValidationError("/sandbox run requires a purpose.")
    from vnalpha.sandbox.execution_service import SandboxExecutionService

    preview = SandboxExecutionService(conn, surface=surface).prepare_job(purpose)
    return CommandResult(
        status="SUCCESS",
        title="/sandbox run",
        summary=(
            f"Sandbox job {preview.job.job_id} is queued and awaiting approval; "
            "execution has not started."
        ),
        panels=[
            ResultPanel(
                title="Sandbox Job",
                content={
                    "job_id": str(preview.job.job_id),
                    "run_id": str(preview.job.run_id),
                    "correlation_id": str(preview.job.correlation_id),
                    "purpose": preview.job.purpose,
                    "status": preview.job.status.value,
                    "code_digest": preview.job.code_digest,
                    "code_summary": preview.code_summary,
                    "input_references": list(preview.job.filesystem_policy.approved_read_paths),
                    "resource_limits": {
                        "cpu_millis": preview.job.resource_limits.cpu_millis,
                        "memory_mb": preview.job.resource_limits.memory_mb,
                        "timeout_seconds": preview.job.resource_limits.timeout_seconds,
                    },
                    "image_digest": str(preview.image).split("@", 1)[1],
                },
            )
        ],
    )


def _job_id_argument(parsed: ParsedCommand, subcommand: str) -> SandboxJobId:
    if len(parsed.positional) != 2 or parsed.options or parsed.filters:
        raise CommandValidationError(
            f"/sandbox {subcommand} requires exactly one job ID."
        )
    return SandboxJobId(parsed.positional[1])


def _validate_latest_query(parsed: ParsedCommand) -> None:
    if (
        len(parsed.positional) != 1
        or parsed.filters
        or parsed.options != {"latest": True}
    ):
        raise CommandValidationError("/sandbox list requires exactly --latest.")


def _status_result(
    record: SandboxJobRecord | None, *, title: str = "/sandbox status"
) -> CommandResult:
    if record is None:
        return CommandResult(
            status="EMPTY_RESULT", title=title, summary="Sandbox job not found."
        )
    return CommandResult(
        status="SUCCESS",
        title=title,
        summary=f"Sandbox job {record.job_id} is {record.status.value}.",
        panels=[ResultPanel(title="Sandbox Job", content=_record_metadata(record))],
    )


def _artifact_result(record: SandboxJobRecord | None) -> CommandResult:
    if record is None:
        return CommandResult(
            status="EMPTY_RESULT",
            title="/sandbox artifact",
            summary="Sandbox job not found.",
        )
    root = f"logs/runs/{record.run_id}/sandbox/{record.job_id}"
    layout = SandboxArtifactLayout()
    return CommandResult(
        status="SUCCESS",
        title="/sandbox artifact",
        summary=f"Canonical sandbox artifacts for {record.job_id}.",
        panels=[
            ResultPanel(
                title="Sandbox Artifacts",
                content={
                    "root": root,
                    "manifest": f"{root}/{layout.manifest}",
                    "status": record.status.value,
                    "correlation_id": record.correlation_id,
                },
            )
        ],
    )


def _record_metadata(record: SandboxJobRecord) -> dict[str, str]:
    return {
        "job_id": record.job_id,
        "run_id": record.run_id,
        "correlation_id": record.correlation_id,
        "purpose": record.purpose,
        "status": record.status.value,
        "code_digest": record.code_digest,
    }
