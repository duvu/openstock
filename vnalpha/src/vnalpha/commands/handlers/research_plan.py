from __future__ import annotations

from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_workflow_common import (
    format_number,
    optional_date,
    validate_workflow_command,
    workflow_result,
    workflow_tool_executor,
)
from vnalpha.commands.models import (
    CommandResult,
    ParsedCommand,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_symbol


def handle_research_plan(parsed: ParsedCommand, conn=None, **kwargs):
    if conn is None:
        return _database_missing()

    validate_workflow_command(
        parsed,
        allowed_options={"date", "with-evidence", "with-regime"},
        maximum_positionals=1,
    )
    if len(parsed.positional) != 1:
        raise CommandValidationError("/research-plan requires exactly one symbol.")

    symbol = normalize_symbol(parsed.positional[0])
    date = optional_date(parsed)
    tool_executor = workflow_tool_executor(kwargs, title="/research-plan")
    if isinstance(tool_executor, CommandResult):
        return tool_executor

    output = tool_executor.call(
        "scenario.generate_research_plan",
        symbol=symbol,
        date=date,
    )
    data = output.data if isinstance(output.data, dict) else None
    artifact_id = (
        f"scenario.generate_research_plan:{symbol}:{(data or {}).get('as_of_date') or date or 'latest'}"
    )
    return workflow_result(
        title=f"/research-plan — {symbol}",
        subject=symbol,
        view="scenario_plan",
        artifact_id=artifact_id,
        output=output,
        data=data,
        tables=_scenario_tables(data),
        panels=_scenario_panels(data),
    )


def _scenario_panels(data: dict[str, Any] | None) -> list[ResultPanel]:
    if data is None:
        return []
    current_setup = (
        data.get("current_setup") if isinstance(data.get("current_setup"), dict) else {}
    )
    key_levels = (
        data.get("key_levels") if isinstance(data.get("key_levels"), dict) else {}
    )
    risk_reward = (
        data.get("risk_reward_context")
        if isinstance(data.get("risk_reward_context"), dict)
        else {}
    )
    checklist = data.get("checklist") if isinstance(data.get("checklist"), list) else []
    return [
        ResultPanel(
            title="Current setup",
            content={
                "candidate_class": current_setup.get("candidate_class"),
                "setup_type": current_setup.get("setup_type"),
                "score": format_number(current_setup.get("score")),
                "risk_flags": ", ".join(current_setup.get("risk_flags") or []) or "—",
            },
        ),
        ResultPanel(
            title="Key levels",
            content={
                "latest_close": format_number(key_levels.get("latest_close")),
                "support_20d": format_number(key_levels.get("support_20d")),
                "resistance_20d": format_number(key_levels.get("resistance_20d")),
                "ma20": format_number(key_levels.get("ma20")),
                "ma50": format_number(key_levels.get("ma50")),
                "atr14": format_number(key_levels.get("atr14")),
            },
        ),
        ResultPanel(
            title="Risk and checklist",
            content={
                "reward_risk_ratio": format_number(
                    risk_reward.get("reward_risk_ratio")
                ),
                "reward_distance": format_number(risk_reward.get("reward_distance")),
                "risk_distance": format_number(risk_reward.get("risk_distance")),
                "basis": risk_reward.get("basis"),
                "checklist": "; ".join(str(item) for item in checklist) or "—",
            },
        ),
    ]


def _scenario_tables(data: dict[str, Any] | None) -> list[ResultTable]:
    if data is None:
        return []
    scenarios = data.get("scenarios") if isinstance(data.get("scenarios"), list) else []
    rows = [
        [
            item.get("name", ""),
            "; ".join(str(condition) for condition in item.get("conditions") or []),
            item.get("interpretation", ""),
        ]
        for item in scenarios
        if isinstance(item, dict)
    ]
    if not rows:
        return []
    return [
        ResultTable(
            title="Scenario branches",
            columns=[
                ResultColumn("name", "Branch"),
                ResultColumn("conditions", "Conditions"),
                ResultColumn("interpretation", "Interpretation"),
            ],
            rows=rows,
        )
    ]


def _database_missing():
    from vnalpha.tools.models import ToolOutput

    return workflow_result(
        title="/research-plan",
        subject="",
        view="scenario_plan",
        artifact_id="scenario.generate_research_plan:unavailable",
        output=ToolOutput(summary="No database connection."),
        data=None,
    )
