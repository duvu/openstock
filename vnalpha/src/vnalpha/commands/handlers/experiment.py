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
            "Experiment subcommand is required: indicator or backtest."
        )
    service = ResearchWorkflowService(conn)
    subcommand = parsed.positional[0].lower()
    if subcommand == "indicator":
        return _indicator(parsed, service)
    if subcommand == "backtest":
        return _backtest(parsed, ResearchStudyService(conn))
    raise CommandValidationError(
        "Unsupported /experiment subcommand. Supported: indicator, backtest."
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


def _backtest(parsed: ParsedCommand, service: ResearchStudyService) -> CommandResult:
    allowed = {"horizon", "start", "end"}
    if parsed.filters or set(parsed.options) - allowed:
        raise CommandValidationError(
            "/experiment backtest supports --horizon, --start, and --end."
        )
    description = " ".join(parsed.positional[1:]).strip()
    if not description:
        raise CommandValidationError(
            "/experiment backtest requires an event-study description."
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
        "/experiment backtest", outcome.artifact, "Offline research event study"
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
