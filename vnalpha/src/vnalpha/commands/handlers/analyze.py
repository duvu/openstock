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
    CommandStatus,
    ParsedCommand,
    ResultPanel,
)
from vnalpha.commands.normalizers import normalize_symbol
from vnalpha.data_availability.deep_readiness import (
    ContextRequirement,
    ensure_deep_analysis_ready,
)


def handle_analyze(parsed: ParsedCommand, conn=None, **kwargs):
    if conn is None:
        return workflow_result(
            title="/analyze",
            subject="",
            view="deep_analysis",
            artifact_id="analysis.deep_symbol:unavailable",
            output=kwargs.get("tool_output")
            or _empty_tool_output("No database connection."),
            data=None,
        )

    validate_workflow_command(
        parsed,
        allowed_options={"date", "with-sector", "with-regime"},
        maximum_positionals=1,
    )
    if len(parsed.positional) != 1:
        raise CommandValidationError("/analyze requires exactly one symbol.")

    symbol = normalize_symbol(parsed.positional[0])
    date = optional_date(parsed)
    market_regime_requirement = _requirement(parsed, "with-regime")
    sector_strength_requirement = _requirement(parsed, "with-sector")
    readiness = ensure_deep_analysis_ready(
        conn,
        symbol,
        date,
        market_regime_requirement=market_regime_requirement,
        sector_strength_requirement=sector_strength_requirement,
    )
    readiness_panel = ResultPanel(
        title="Data Readiness",
        content=readiness.to_panel_dict(),
    )
    if not readiness.is_ready:
        return CommandResult(
            status=CommandStatus.FAILED,
            title=f"/analyze — {symbol}",
            summary=readiness.failure_summary(),
            panels=[readiness_panel],
            warnings=[*readiness.warnings, *readiness.errors],
        )
    tool_executor = workflow_tool_executor(kwargs, title="/analyze")
    if isinstance(tool_executor, CommandResult):
        return tool_executor

    output = tool_executor.call(
        "analysis.deep_symbol",
        symbol=symbol,
        date=date,
        market_regime_requirement=market_regime_requirement,
        sector_strength_requirement=sector_strength_requirement,
    )
    data = output.data if isinstance(output.data, dict) else None
    if data is None:
        return workflow_result(
            title=f"/analyze — {symbol}",
            subject=symbol,
            view="deep_analysis",
            artifact_id=f"analysis.deep_symbol:{symbol}:{date or 'latest'}",
            output=output,
            data=None,
            panels=[readiness_panel],
        )

    artifact_id = (
        f"analysis.deep_symbol:{symbol}:{data.get('as_of_date') or date or 'latest'}"
    )
    return workflow_result(
        title=f"/analyze — {symbol}",
        subject=symbol,
        view="deep_analysis",
        artifact_id=artifact_id,
        output=output,
        data=data,
        panels=[readiness_panel, *_analysis_panels(data)],
    )


def _analysis_panels(data: dict[str, Any]) -> list[ResultPanel]:
    candidate = data.get("candidate") if isinstance(data.get("candidate"), dict) else {}
    feature = (
        data.get("feature_context")
        if isinstance(data.get("feature_context"), dict)
        else {}
    )
    levels = data.get("levels") if isinstance(data.get("levels"), dict) else {}
    freshness = data.get("freshness") if isinstance(data.get("freshness"), dict) else {}
    quality = data.get("quality") if isinstance(data.get("quality"), dict) else {}
    market = (
        data.get("market_context")
        if isinstance(data.get("market_context"), dict)
        else {}
    )
    sector = (
        data.get("sector_context")
        if isinstance(data.get("sector_context"), dict)
        else {}
    )
    evidence = (
        candidate.get("evidence_json")
        if isinstance(candidate.get("evidence_json"), dict)
        else {}
    )
    return [
        ResultPanel(
            title="Quality and freshness",
            content={
                "quality_status": quality.get("status"),
                "price_bar_date": freshness.get("price_bar_date"),
                "feature_generated_at": freshness.get("feature_generated_at"),
                "score_generated_at": freshness.get("score_generated_at"),
            },
        ),
        ResultPanel(
            title="Trend and momentum",
            content={
                "candidate_class": candidate.get("candidate_class"),
                "setup_type": candidate.get("setup_type"),
                "score": format_number(candidate.get("score")),
                "ma20_slope": format_number(feature.get("ma20_slope")),
                "ma50_slope": format_number(feature.get("ma50_slope")),
                "return_20d": format_number(feature.get("return_20d")),
                "return_60d": format_number(feature.get("return_60d")),
                "close_strength": format_number(feature.get("close_strength")),
            },
        ),
        ResultPanel(
            title="Relative strength and volume",
            content={
                "benchmark": feature.get("lineage", {}).get(
                    "benchmark_symbol", "VNINDEX"
                ),
                "rs_20d": format_number(feature.get("rs_20d_vs_vnindex")),
                "rs_60d": format_number(feature.get("rs_60d_vs_vnindex")),
                "sector_alignment": sector.get("sector"),
                "sector_rank": sector.get("rank"),
                "volume_ratio": format_number(feature.get("volume_ratio")),
                "volume_ma20": format_number(feature.get("volume_ma20")),
            },
        ),
        ResultPanel(
            title="Volatility and levels",
            content={
                "atr14": format_number(feature.get("atr14")),
                "volatility_20d": format_number(feature.get("volatility_20d")),
                "latest_close": format_number(levels.get("latest_close")),
                "support_20d": format_number(levels.get("support_20d")),
                "resistance_20d": format_number(levels.get("resistance_20d")),
                "high_60d": format_number(levels.get("high_60d")),
                "low_60d": format_number(levels.get("low_60d")),
            },
        ),
        ResultPanel(
            title="Setup quality",
            content={
                "trend_alignment": format_number(candidate.get("trend_score")),
                "relative_strength_quality": format_number(
                    candidate.get("relative_strength_score")
                ),
                "volume_quality": format_number(candidate.get("volume_score")),
                "base_quality": format_number(candidate.get("base_score")),
                "breakout_quality": format_number(candidate.get("breakout_score")),
                "risk_quality": format_number(candidate.get("risk_quality_score")),
                "component_note": evidence.get("component_note")
                or "Composite setup quality remains descriptive only.",
            },
        ),
        ResultPanel(
            title="Scenario summary",
            content={
                "market_regime": market.get("regime"),
                "market_trend": market.get("trend"),
                "confirmation_condition": _monitoring_condition(levels, feature),
                "invalidation_condition": _invalidation_condition(levels, feature),
                "missing_data": ", ".join(data.get("missing_data") or []) or "—",
            },
        ),
    ]


def _monitoring_condition(levels: dict[str, Any], feature: dict[str, Any]) -> str:
    resistance = levels.get("resistance_20d")
    latest_close = levels.get("latest_close") or feature.get("close")
    if resistance is None or latest_close is None:
        return "Monitor for persisted price confirmation against resistance or MA20."
    return (
        "Monitor whether persisted close "
        f"{format_number(latest_close)} remains above resistance "
        f"{format_number(resistance)}."
    )


def _invalidation_condition(levels: dict[str, Any], feature: dict[str, Any]) -> str:
    support = levels.get("support_20d")
    ma50 = feature.get("ma50")
    if support is None and ma50 is None:
        return "Monitor for a deterioration in support or long-trend context."
    if support is None:
        return f"Monitor whether persisted close loses MA50 {format_number(ma50)}."
    return f"Monitor whether persisted close loses support {format_number(support)}."


def _empty_tool_output(summary: str):
    from vnalpha.tools.models import ToolOutput

    return ToolOutput(summary=summary)


def _requirement(parsed: ParsedCommand, option: str) -> ContextRequirement:
    return (
        ContextRequirement.REQUIRED
        if parsed.options.get(option)
        else ContextRequirement.NOT_REQUESTED
    )
