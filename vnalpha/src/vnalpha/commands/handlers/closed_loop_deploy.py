from __future__ import annotations

from vnalpha.closed_loop.errors import ClosedLoopError
from vnalpha.closed_loop.models import PromotableArtifactType
from vnalpha.closed_loop.validation import resolve_artifact_root
from vnalpha.commands.handlers.closed_loop_common import (
    failed,
    invalid,
    path_value,
    report_payload,
    service,
)
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel


def handle_validate(parsed: ParsedCommand, **kwargs) -> CommandResult:
    if len(parsed.positional) != 2 or parsed.positional[0].lower() != "run":
        return invalid(
            "Unsupported /validate subcommand. Supported: run <artifact-id>."
        )
    current_service = service()
    artifact_root = path_value(kwargs.get("artifact_root"))
    try:
        report = current_service.validate(
            parsed.positional[1], artifact_root=artifact_root
        )
    except (ClosedLoopError, ValueError) as exc:
        return failed("/validate run", str(exc))
    return CommandResult(
        status="SUCCESS" if report.passed else "FAILED",
        title="/validate run",
        summary=(
            f"Artifact {report.artifact_id} passed the validation gate."
            if report.passed
            else f"Artifact {report.artifact_id} failed the validation gate."
        ),
        panels=[ResultPanel(title="Validation Report", content=report_payload(report))],
    )


def handle_deploy(parsed: ParsedCommand, **kwargs) -> CommandResult:
    if not parsed.positional:
        return invalid("/deploy requires verify, promote, or rollback.")
    current_service = service()
    subcommand = parsed.positional[0].lower()
    try:
        if subcommand == "verify":
            return _verify(current_service, parsed, kwargs)
        if subcommand == "promote":
            return _promote(current_service, parsed)
        if subcommand == "rollback":
            return _rollback(current_service, parsed)
    except (ClosedLoopError, ValueError) as exc:
        return failed("/deploy", str(exc))
    return invalid(
        "Unsupported /deploy subcommand. Supported: verify, promote, rollback."
    )


def _verify(current_service, parsed: ParsedCommand, kwargs: dict) -> CommandResult:
    if len(parsed.positional) != 2:
        return invalid(
            "/deploy verify requires exactly one research artifact candidate."
        )
    if set(parsed.options) - {"deployment-id", "candidate-type"}:
        return invalid("Unsupported /deploy verify option.")
    candidate = parsed.positional[1]
    root = path_value(kwargs.get("artifact_root")) or resolve_artifact_root(
        current_service.store.root, candidate
    )
    deployment_id = parsed.options.get("deployment-id")
    candidate_type_value = parsed.options.get("candidate-type")
    try:
        candidate_type = (
            PromotableArtifactType(candidate_type_value)
            if isinstance(candidate_type_value, str)
            else None
        )
    except ValueError:
        return invalid(f"Unsupported research artifact type: {candidate_type_value}")
    verification = current_service.verify(
        candidate,
        artifact_root=root,
        candidate_type=candidate_type,
        deployment_id=deployment_id if isinstance(deployment_id, str) else None,
    )
    return CommandResult(
        status="SUCCESS" if verification.passed else "FAILED",
        title="/deploy verify",
        summary=(
            f"Research artifact {candidate} is ready for promotion."
            if verification.passed
            else f"Research artifact {candidate} is not ready for promotion."
        ),
        panels=[
            ResultPanel(
                title="Promotion Verification",
                content=verification.model_dump(mode="json"),
            )
        ],
    )


def _promote(current_service, parsed: ParsedCommand) -> CommandResult:
    if len(parsed.positional) != 2:
        return invalid("/deploy promote requires a candidate and --deployment-id.")
    if set(parsed.options) - {"deployment-id", "previous"}:
        return invalid("Unsupported /deploy promote option.")
    deployment_id = parsed.options.get("deployment-id")
    if not isinstance(deployment_id, str):
        return invalid("/deploy promote requires --deployment-id <id>.")
    previous = parsed.options.get("previous")
    state = current_service.promote(
        parsed.positional[1],
        deployment_id=deployment_id,
        previous_candidate=previous if isinstance(previous, str) else None,
    )
    return CommandResult(
        status="SUCCESS",
        title="/deploy promote",
        summary=f"Research artifact {state.candidate} promoted.",
        panels=[ResultPanel(title="Deploy Log", content=state.model_dump(mode="json"))],
    )


def _rollback(current_service, parsed: ParsedCommand) -> CommandResult:
    if len(parsed.positional) != 2:
        return invalid("/deploy rollback requires exactly one deployment ID.")
    if set(parsed.options) - {"reason"}:
        return invalid("Unsupported /deploy rollback option.")
    reason = parsed.options.get("reason", "")
    state = current_service.rollback(
        parsed.positional[1], reason=reason if isinstance(reason, str) else ""
    )
    return CommandResult(
        status="SUCCESS",
        title="/deploy rollback",
        summary=f"Research artifact {state.candidate} rolled back.",
        panels=[
            ResultPanel(title="Rollback Log", content=state.model_dump(mode="json"))
        ],
    )
