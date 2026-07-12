from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_context_validation import validate_command_input
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultArtifact,
    ResultPanel,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_date
from vnalpha.tools.models import ToolOutput

_SUPPORTED_SETUP_TYPES = frozenset(
    {
        "ACCUMULATION_BASE",
        "BREAKOUT_ATTEMPT",
        "MOMENTUM_CONTINUATION",
        "PULLBACK_TO_TREND",
        "MEAN_REVERSION",
        "UNCLASSIFIED",
    }
)


def workflow_tool_executor(
    kwargs: dict[str, Any], *, title: str
) -> Any | CommandResult:
    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title=title,
            summary="No tool executor available.",
        )
    return tool_executor


def validate_workflow_command(
    parsed: ParsedCommand,
    *,
    allowed_options: set[str],
    maximum_positionals: int,
) -> None:
    validate_command_input(
        parsed,
        allowed_options,
        maximum_positionals=maximum_positionals,
    )


def optional_date(parsed: ParsedCommand) -> str | None:
    value = parsed.options.get("date")
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError("--date requires a YYYY-MM-DD value.")
    return normalize_date(value)


def positive_int_option(
    parsed: ParsedCommand,
    option_name: str,
    *,
    maximum: int,
) -> int | None:
    value = parsed.options.get(option_name)
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError(f"--{option_name} requires a positive integer.")
    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise CommandValidationError(
            f"--{option_name} requires a positive integer."
        ) from exc
    if parsed_value <= 0 or parsed_value > maximum:
        raise CommandValidationError(
            f"--{option_name} must be between 1 and {maximum}."
        )
    return parsed_value


def workflow_status(data: object, warnings: list[str]) -> CommandStatus:
    if not isinstance(data, Mapping) or not data.get("available"):
        return CommandStatus.EMPTY_RESULT
    missing_data = data.get("missing_data")
    if warnings or (isinstance(missing_data, list) and missing_data):
        return CommandStatus.PARTIAL
    return CommandStatus.SUCCESS


def workflow_metadata(
    *,
    view: str,
    artifact_id: str,
    subject: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    missing_data = data.get("missing_data")
    caveats = data.get("caveats")
    artifact_refs = data.get("artifact_refs")
    return {
        "research_view": view,
        "artifact_id": artifact_id,
        "subject": subject,
        "as_of_date": data.get("as_of_date"),
        "workflow_status": "partial"
        if isinstance(missing_data, list) and missing_data
        else "complete",
        "missing_data": list(missing_data)
        if isinstance(missing_data, list)
        else [],
        "artifact_refs": list(artifact_refs)
        if isinstance(artifact_refs, list)
        else [],
        "caveats": list(caveats) if isinstance(caveats, list) else [],
    }


def workflow_artifact(
    *,
    artifact_id: str,
    data: Mapping[str, Any],
) -> list[ResultArtifact]:
    return [ResultArtifact(name=artifact_id, data=dict(data))]


def workflow_result(
    *,
    title: str,
    subject: str,
    view: str,
    artifact_id: str,
    output: ToolOutput,
    data: Mapping[str, Any] | None,
    tables: list[ResultTable] | None = None,
    panels: list[ResultPanel] | None = None,
    extra_warnings: list[str] | None = None,
) -> CommandResult:
    warnings = list(output.warnings)
    if extra_warnings:
        warnings.extend(extra_warnings)
    if data is None:
        return CommandResult(
            status=CommandStatus.FAILED,
            title=title,
            summary=output.summary or "No workflow payload was returned.",
            warnings=warnings,
        )

    return CommandResult(
        status=workflow_status(data, warnings),
        title=title,
        summary=output.summary,
        tables=tables or [],
        panels=panels or [],
        artifacts=workflow_artifact(artifact_id=artifact_id, data=data),
        warnings=warnings,
        metadata=workflow_metadata(
            view=view,
            artifact_id=artifact_id,
            subject=subject,
            data=data,
        ),
    )


def format_number(value: object, *, digits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def format_percent(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def symbol_or_setup_token(value: str) -> tuple[str, bool]:
    normalized = value.strip().upper()
    return normalized, normalized in _SUPPORTED_SETUP_TYPES
