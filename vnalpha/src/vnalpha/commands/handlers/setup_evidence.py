from __future__ import annotations

from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.handlers.research_workflow_common import (
    format_number,
    format_percent,
    optional_date,
    positive_int_option,
    symbol_or_setup_token,
    validate_workflow_command,
    workflow_result,
    workflow_tool_executor,
)
from vnalpha.commands.models import (
    CommandResult,
    CommandStatus,
    ParsedCommand,
    ResultColumn,
    ResultPanel,
    ResultTable,
)
from vnalpha.commands.normalizers import normalize_symbol
from vnalpha.data_availability.deep_readiness import ensure_deep_analysis_ready


def handle_setup_evidence(parsed: ParsedCommand, conn=None, **kwargs):
    if conn is None:
        return _database_missing()

    validate_workflow_command(
        parsed,
        allowed_options={"date", "horizon", "regime"},
        maximum_positionals=1,
    )
    if len(parsed.positional) != 1:
        raise CommandValidationError("/setup-evidence requires a setup type or symbol.")

    horizon = positive_int_option(parsed, "horizon", maximum=252)
    date = optional_date(parsed)
    requested_token = parsed.positional[0]
    normalized_token, is_setup_type = symbol_or_setup_token(requested_token)
    tool_executor = workflow_tool_executor(kwargs, title="/setup-evidence")
    if isinstance(tool_executor, CommandResult):
        return tool_executor

    setup_type = normalized_token
    extra_warnings: list[str] = []
    if not is_setup_type:
        readiness = ensure_deep_analysis_ready(conn, normalized_token, date)
        readiness_panel = ResultPanel("Data Readiness", readiness.to_panel_dict())
        if not readiness.is_ready:
            return CommandResult(
                status=CommandStatus.FAILED,
                title=f"/setup-evidence — {normalized_token}",
                summary=readiness.failure_summary(),
                panels=[readiness_panel],
                warnings=[*readiness.warnings, *readiness.errors],
            )
        date = readiness.resolved_date
        setup_type = _setup_type_for_symbol(tool_executor, normalized_token, date)
        extra_warnings.append(
            f"Resolved {normalize_symbol(requested_token)} to setup type {setup_type} from persisted analysis."
        )
    if parsed.options.get("regime") not in (None, False):
        extra_warnings.append(
            "Regime-specific filtering is not yet available in persisted setup evidence output."
        )

    output = tool_executor.call(
        "evidence.get_setup_history",
        setup_type=setup_type,
        horizon_sessions=horizon,
        date=date,
    )
    data = output.data if isinstance(output.data, dict) else None
    artifact_id = f"evidence.get_setup_history:{setup_type}:{(data or {}).get('horizon_sessions') or horizon or 20}:{(data or {}).get('as_of_date') or date or 'latest'}"
    return workflow_result(
        title=f"/setup-evidence — {setup_type}",
        subject=setup_type,
        view="setup_evidence",
        artifact_id=artifact_id,
        output=output,
        data=data,
        tables=_evidence_tables(data),
        panels=([readiness_panel] if not is_setup_type else [])
        + _evidence_panels(data),
        extra_warnings=extra_warnings,
    )


def _setup_type_for_symbol(tool_executor, symbol: str, date: str | None) -> str:
    output = tool_executor.call("analysis.deep_symbol", symbol=symbol, date=date)
    data = output.data if isinstance(output.data, dict) else None
    candidate = data.get("candidate") if isinstance(data, dict) else None
    if not isinstance(candidate, dict):
        raise CommandValidationError(
            f"No persisted candidate setup is available for symbol {symbol}."
        )
    setup_type = candidate.get("setup_type")
    if not isinstance(setup_type, str) or not setup_type.strip():
        raise CommandValidationError(
            f"No persisted setup type is available for symbol {symbol}."
        )
    return setup_type.strip().upper()


def _evidence_panels(data: dict[str, Any] | None) -> list[ResultPanel]:
    if data is None:
        return []
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    lineage = data.get("lineage") if isinstance(data.get("lineage"), dict) else {}
    return [
        ResultPanel(
            title="Sample definition",
            content={
                "setup_type": data.get("setup_type"),
                "horizon_sessions": data.get("horizon_sessions"),
                "sample_size": evidence.get("candidate_count"),
                "as_of_date": data.get("as_of_date"),
                "computed_at": data.get("freshness", {}).get("computed_at")
                if isinstance(data.get("freshness"), dict)
                else None,
            },
        ),
        ResultPanel(
            title="Lineage",
            content={
                "evaluation_run_id": lineage.get("evaluation_run_id"),
                "evaluator_version": lineage.get("evaluator_version"),
                "metric_policy_version": lineage.get("metric_policy_version"),
            },
        ),
    ]


def _evidence_tables(data: dict[str, Any] | None) -> list[ResultTable]:
    if data is None:
        return []
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    rows = [
        ["avg_forward_return", format_number(evidence.get("avg_forward_return"))],
        ["median_forward_return", format_number(evidence.get("median_forward_return"))],
        ["avg_excess_return", format_number(evidence.get("avg_excess_return"))],
        ["hit_rate", format_percent(evidence.get("hit_rate"))],
        ["failure_rate", format_percent(evidence.get("failure_rate"))],
        ["avg_max_drawdown", format_number(evidence.get("avg_max_drawdown"))],
    ]
    return [
        ResultTable(
            title="Historical outcome metrics",
            columns=[
                ResultColumn("metric", "Metric"),
                ResultColumn("value", "Value"),
            ],
            rows=rows,
        )
    ]


def _database_missing():
    from vnalpha.tools.models import ToolOutput

    return workflow_result(
        title="/setup-evidence",
        subject="",
        view="setup_evidence",
        artifact_id="evidence.get_setup_history:unavailable",
        output=ToolOutput(summary="No database connection."),
        data=None,
    )
