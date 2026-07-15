from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_automation_common import (
    parse_optional_date,
    positive_integer,
    workflow_warnings,
)
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.research_automation.study_service import ResearchStudyService
from vnalpha.research_automation.workflow_service import ResearchWorkflowService


def handle_experiment(parsed: ParsedCommand, conn=None, **_kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED", title="/experiment", summary="No database connection."
        )
    if not parsed.positional:
        raise CommandValidationError(
            "Experiment subcommand is required: indicator or event-study."
        )
    service = ResearchWorkflowService(conn)
    subcommand = parsed.positional[0].lower()
    if subcommand == "indicator":
        return _indicator(parsed, service)
    if subcommand == "event-study":
        return _event_study(parsed, ResearchStudyService(conn))
    if subcommand == "backtest":
        raise CommandValidationError(
            "The /experiment backtest alias is disabled because OpenStock does not "
            "yet implement a point-in-time strategy simulator. Use /experiment "
            "event-study with an allowlisted condition such as "
            "'rs_20d_vs_vnindex > 0'."
        )
    raise CommandValidationError(
        "Unsupported /experiment subcommand. Supported: indicator, event-study."
    )


def _indicator(
    parsed: ParsedCommand, service: ResearchWorkflowService
) -> CommandResult:
    allowed = {"universe", "start", "end"}
    if parsed.filters or set(parsed.options) - allowed:
        raise CommandValidationError(
            "/experiment indicator supports --universe, --start, and --end."
        )
    description = " ".join(parsed.positional[1:]).strip()
    if not description:
        raise CommandValidationError("/experiment indicator requires a description.")
    universe = parsed.options.get("universe")
    if universe is True:
        raise CommandValidationError("--universe requires a value.")
    try:
        outcome = service.indicator(
            description,
            universe=str(universe) if universe else None,
            start_date=parse_optional_date(parsed.options.get("start"), "start"),
            end_date=parse_optional_date(parsed.options.get("end"), "end"),
        )
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    return _result("/experiment indicator", outcome.artifact, "Indicator experiment")


def _event_study(parsed: ParsedCommand, service: ResearchStudyService) -> CommandResult:
    allowed = {"horizon", "start", "end"}
    if set(parsed.options) - allowed:
        raise CommandValidationError(
            "/experiment event-study supports --horizon, --start, and --end."
        )
    condition_parts: list[str] = []
    positional_condition = " ".join(parsed.positional[1:]).strip()
    if positional_condition:
        condition_parts.append(positional_condition)
    for item in parsed.filters:
        operator = "==" if item.op == "=" else item.op
        condition_parts.append(f"{item.key} {operator} {item.value}")
    description = " AND ".join(condition_parts)
    if not description:
        raise CommandValidationError(
            "/experiment event-study requires an allowlisted numeric condition."
        )
    try:
        outcome = service.event_study(
            description,
            horizon=positive_integer(parsed.options.get("horizon"), "horizon", 10),
            start_date=parse_optional_date(parsed.options.get("start"), "start"),
            end_date=parse_optional_date(parsed.options.get("end"), "end"),
        )
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    return _result(
        "/experiment event-study", outcome.artifact, "Offline research event study"
    )


def _result(title: str, artifact, label: str) -> CommandResult:
    succeeded = artifact.status.value == "succeeded"
    return CommandResult(
        status="SUCCESS" if succeeded else "PARTIAL",
        title=title,
        summary=f"{label} {artifact.artifact_id} completed as research-only evidence.",
        panels=[
            ResultPanel(
                title=label,
                content={
                    "artifact_id": artifact.artifact_id,
                    "status": artifact.status.value,
                    "metrics": dict(artifact.metrics),
                    "lineage": dict(artifact.lineage),
                    "dataset_refs": [
                        item.snapshot_id for item in artifact.input_datasets
                    ],
                    "research_only": True,
                },
            )
        ],
        warnings=workflow_warnings(artifact),
    )


__all__ = ["handle_experiment"]
