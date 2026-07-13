from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_automation_common import (
    parse_optional_date,
    workflow_warnings,
)
from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.research_automation.workflow_service import ResearchWorkflowService


def handle_pattern(parsed: ParsedCommand, conn=None, **_kwargs) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED", title="/pattern", summary="No database connection."
        )
    if not parsed.positional or parsed.positional[0].lower() != "scan":
        raise CommandValidationError(
            "Unsupported /pattern subcommand. Supported: scan."
        )
    if parsed.filters or set(parsed.options) - {"universe", "date"}:
        raise CommandValidationError("/pattern scan supports --universe and --date.")
    description = " ".join(parsed.positional[1:]).strip()
    if not description:
        raise CommandValidationError("/pattern scan requires a pattern description.")
    universe = parsed.options.get("universe")
    if universe is True:
        raise CommandValidationError("--universe requires a value.")
    try:
        outcome = ResearchWorkflowService(conn).pattern(
            description,
            universe=str(universe) if universe else None,
            scan_date=parse_optional_date(parsed.options.get("date"), "date"),
        )
    except ValueError as exc:
        raise CommandValidationError(str(exc)) from exc
    artifact = outcome.artifact
    return CommandResult(
        status="SUCCESS" if artifact.status.value == "succeeded" else "PARTIAL",
        title="/pattern scan",
        summary=f"Pattern scan persisted {len(outcome.rows)} research candidates; no trading action was produced.",
        tables=[
            ResultTable(
                title="Research Candidates",
                columns=[
                    ResultColumn("symbol", "Symbol"),
                    ResultColumn("base_range", "Base Range 30D"),
                    ResultColumn("volatility", "Volatility 20D"),
                    ResultColumn("volume_ratio", "Volume Ratio"),
                ],
                rows=[list(row) for row in outcome.rows],
            )
        ],
        panels=[
            ResultPanel(
                title="Pattern Artifact",
                content={
                    "artifact_id": artifact.artifact_id,
                    "status": artifact.status.value,
                    "research_only": True,
                },
            )
        ],
        warnings=workflow_warnings(artifact),
    )


__all__ = ["handle_pattern"]
