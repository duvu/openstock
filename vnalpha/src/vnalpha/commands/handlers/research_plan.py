"""Research-only `/research-plan` command handler."""

from __future__ import annotations

from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.research_intelligence.scenario_policy import (
    validate_research_only_language,
)


def handle_research_plan(parsed: ParsedCommand, conn=None, **kwargs) -> CommandResult:
    """Render a policy-validated scenario plan from the local scenario tool."""
    if conn is None:
        return CommandResult(
            CommandStatus.FAILED, "/research-plan", summary="No database connection."
        )
    if not parsed.positional:
        return CommandResult(
            CommandStatus.VALIDATION_ERROR,
            "/research-plan",
            summary=(
                "Usage: /research-plan SYMBOL [--date DATE] "
                "[--with-evidence] [--with-regime]"
            ),
        )
    tool_executor = kwargs.get("tool_executor")
    if tool_executor is None:
        return CommandResult(
            CommandStatus.FAILED,
            "/research-plan",
            summary="No tool executor available.",
        )

    symbol = normalize_symbol(parsed.positional[0])
    date = normalize_date(parsed.options.get("date"))
    output = tool_executor.call(
        "scenario.generate_research_plan",
        symbol=symbol,
        date=date,
        with_evidence=bool(parsed.options.get("with-evidence", False)),
        with_regime=bool(parsed.options.get("with-regime", False)),
        correlation_id=kwargs.get("session_id"),
    )
    plan = output.data
    validate_research_only_language(plan)

    panels = [
        ResultPanel(title="Current Setup", content=plan["current_setup"]),
        ResultPanel(title="Key Levels", content=plan["key_levels"]),
        ResultPanel(
            title="Conditions",
            content={
                "confirmation": plan["confirmation_conditions"],
                "invalidation": plan["invalidation_conditions"],
            },
        ),
        ResultPanel(title="Scenario Tree", content=plan["scenario_tree"]),
        ResultPanel(title="Research Estimate", content=plan["risk_reward_estimate"]),
        ResultPanel(title="Checklist", content=plan["checklist"]),
        ResultPanel(
            title="Caveats",
            content={
                "items": plan["caveats"],
                "research_only_language": plan["research_only_language"],
            },
        ),
    ]
    return CommandResult(
        CommandStatus.PARTIAL if output.warnings else CommandStatus.SUCCESS,
        f"/research-plan {symbol} - {date}",
        summary=output.summary,
        panels=panels,
        warnings=output.warnings,
    )
