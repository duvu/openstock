from __future__ import annotations

from vnalpha.closed_loop.bundle import latest_failed_run, run_for_job
from vnalpha.closed_loop.errors import ClosedLoopError
from vnalpha.closed_loop.models import RepairScope
from vnalpha.closed_loop.service import ClosedLoopService
from vnalpha.commands.handlers.closed_loop_common import failed, invalid, service
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel


def handle_repair(parsed: ParsedCommand, **kwargs) -> CommandResult:
    runner = kwargs.get("sandbox_runner")
    current_service = service()
    if not parsed.positional:
        return invalid("/repair requires prepare, status, propose, or apply.")
    subcommand = parsed.positional[0].lower()
    try:
        if subcommand == "prepare":
            return _prepare(current_service, parsed)
        if subcommand == "status":
            return _status(current_service, parsed)
        if subcommand == "propose":
            return _propose(current_service, parsed)
        if subcommand == "apply":
            return _apply(current_service, parsed, runner)
    except (ClosedLoopError, ValueError) as exc:
        return failed("/repair", str(exc))
    return invalid(
        "Unsupported /repair subcommand. Supported: prepare, status, propose, apply."
    )


def _prepare(
    current_service: ClosedLoopService, parsed: ParsedCommand
) -> CommandResult:
    if parsed.options == {"latest": True} and len(parsed.positional) == 1:
        run_dir = latest_failed_run(current_service.store.root)
    elif len(parsed.positional) == 2 and not parsed.options:
        run_dir = run_for_job(current_service.store.root, parsed.positional[1])
    else:
        return invalid("/repair prepare requires --latest or one run/job ID.")
    if run_dir is None or not run_dir.is_dir():
        return CommandResult(
            status="EMPTY_RESULT",
            title="/repair prepare",
            summary="No failed run found.",
        )
    bundle = current_service.prepare_failed_run(run_dir)
    return CommandResult(
        status="SUCCESS",
        title="/repair prepare",
        summary=f"Repair bundle {bundle.repair_id} created.",
        panels=[
            ResultPanel(
                title="Repair Bundle",
                content={
                    "repair_id": bundle.repair_id,
                    "correlation_id": bundle.correlation_id,
                    "failed_job_id": bundle.failed_job_id,
                    "lifecycle_state": current_service.store.current_lifecycle(
                        bundle.repair_id
                    ).state.value,
                },
            )
        ],
    )


def _status(current_service: ClosedLoopService, parsed: ParsedCommand) -> CommandResult:
    if len(parsed.positional) != 2 or parsed.options:
        return invalid("/repair status requires exactly one repair ID.")
    bundle = current_service.store.load_bundle(parsed.positional[1])
    lifecycle = current_service.store.current_lifecycle(bundle.repair_id)
    attempts = current_service.store.list_attempts(bundle.repair_id)
    return CommandResult(
        status="SUCCESS",
        title="/repair status",
        summary=f"Repair {bundle.repair_id} is {lifecycle.state.value}.",
        panels=[
            ResultPanel(
                title="Repair Status",
                content={
                    "repair_id": bundle.repair_id,
                    "correlation_id": bundle.correlation_id,
                    "state": lifecycle.state.value,
                    "attempts": len(attempts),
                },
            )
        ],
    )


def _propose(
    current_service: ClosedLoopService, parsed: ParsedCommand
) -> CommandResult:
    if len(parsed.positional) != 2:
        return invalid("/repair propose requires exactly one repair ID.")
    scope_value = parsed.options.get("scope", RepairScope.SANDBOX_RESEARCH_CODE.value)
    if not isinstance(scope_value, str):
        return invalid("/repair propose --scope must be a supported research scope.")
    patch = parsed.options.get("patch", "")
    patch_text = patch if isinstance(patch, str) else ""
    proposal = current_service.propose(
        parsed.positional[1], scope=RepairScope(scope_value), patch=patch_text
    )
    return CommandResult(
        status="SUCCESS" if proposal.accepted else "FAILED",
        title="/repair propose",
        summary=proposal.rejection_reason or "Repair proposal created.",
        panels=[
            ResultPanel(
                title="Repair Proposal",
                content={
                    "proposal_id": proposal.proposal_id,
                    "repair_id": proposal.repair_id,
                    "scope": proposal.scope.value,
                    "accepted": proposal.accepted,
                    "expected_validation_checks": proposal.expected_validation_checks,
                },
            )
        ],
    )


def _apply(
    current_service: ClosedLoopService, parsed: ParsedCommand, runner
) -> CommandResult:
    if len(parsed.positional) != 2:
        return invalid("/repair apply requires exactly one repair ID and --attempt N.")
    attempt_value = parsed.options.get("attempt")
    if not isinstance(attempt_value, str) or runner is None:
        return invalid(
            "/repair apply requires --attempt N and an approved sandbox runner; no local execution started."
        )
    try:
        attempt = int(attempt_value)
    except ValueError:
        return invalid("/repair apply --attempt must be an integer.")
    record = current_service.apply(parsed.positional[1], attempt=attempt, runner=runner)
    return CommandResult(
        status="SUCCESS" if record.passed else "FAILED",
        title="/repair apply",
        summary=f"Sandbox repair attempt {record.attempt} completed.",
        panels=[
            ResultPanel(
                title="Repair Attempt",
                content={
                    "repair_id": record.repair_id,
                    "attempt": record.attempt,
                    "sandbox_only": record.sandbox_only,
                    "passed": record.passed,
                },
            )
        ],
    )
