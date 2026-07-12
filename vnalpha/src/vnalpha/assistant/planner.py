"""Deterministic plan builder for policy-approved assistant tools."""

from __future__ import annotations

import uuid
from typing import Any

from vnalpha.assistant.errors import PlanBuildError, PlanValidationError
from vnalpha.assistant.models import AssistantPlan, IntentResult, ToolPlanStep


def _resolve_symbol(entities: dict) -> str:
    symbols = entities.get("symbols", [])
    if symbols:
        return str(symbols[0]).strip().upper()
    return str(entities.get("symbol", "")).strip().upper()


def _step(tool: str, args: dict, purpose: str, permission: str) -> ToolPlanStep:
    return ToolPlanStep(
        step_id=str(uuid.uuid4())[:8],
        tool_name=tool,
        arguments=args,
        purpose=purpose,
        required_permission=permission,
    )


def _date_args(entities: dict, **base: Any) -> dict[str, Any]:
    args = dict(base)
    if entities.get("date"):
        args["date"] = entities["date"]
    return args


def _missing_entity_plan(intent: str, entity: str) -> AssistantPlan:
    return AssistantPlan(
        intent=intent,
        steps=[],
        refusal_reason=f"The {intent} workflow requires a {entity}.",
    )


def _build_scan_plan(entities: dict) -> AssistantPlan:
    args = _date_args(entities)
    if entities.get("universe"):
        args["universe"] = entities["universe"]
    return AssistantPlan(
        intent="scan_candidates",
        steps=[
            _step(
                "watchlist.scan",
                args,
                "Retrieve ranked research candidates",
                "READ_WATCHLIST",
            )
        ],
        required_artifacts=["daily_watchlist", "candidate_score"],
    )


def _build_filter_plan(entities: dict) -> AssistantPlan:
    args = _date_args(entities, filters=entities.get("filters", {}))
    return AssistantPlan(
        intent="filter_candidates",
        steps=[
            _step(
                "watchlist.filter",
                args,
                "Filter candidates by criteria",
                "READ_WATCHLIST",
            )
        ],
        required_artifacts=["candidate_score"],
    )


def _build_compare_plan(entities: dict) -> AssistantPlan:
    symbols = [
        str(item).strip().upper() for item in entities.get("symbols", []) if item
    ]
    args = _date_args(entities, symbols=symbols)
    quality_tool = (
        "quality.get_many_status" if len(symbols) > 1 else "quality.get_status"
    )
    quality_args = _date_args(entities, symbols=symbols)
    if quality_tool == "quality.get_status" and symbols:
        quality_args = _date_args(entities, symbol=symbols[0])
    return AssistantPlan(
        intent="compare_symbols",
        steps=[
            _step(
                "candidate.compare",
                args,
                "Compare candidate scores and evidence",
                "READ_SCORE",
            ),
            _step(
                quality_tool,
                quality_args,
                "Check data quality for each symbol",
                "READ_QUALITY",
            ),
        ],
        required_artifacts=["candidate_score", "canonical_ohlcv"],
    )


def _build_explain_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    if not symbol:
        return _missing_entity_plan("explain_symbol", "symbol")
    args = _date_args(entities, symbol=symbol)
    return AssistantPlan(
        intent="explain_symbol",
        steps=[
            _step(
                "candidate.explain",
                args,
                "Explain candidate score and evidence",
                "READ_SCORE",
            ),
            _step(
                "lineage.get_symbol_lineage",
                args,
                "Retrieve data lineage",
                "READ_LINEAGE",
            ),
            _step(
                "quality.get_status", args, "Check data quality status", "READ_QUALITY"
            ),
        ],
        required_artifacts=["candidate_score", "ingestion_run"],
    )


def _build_deep_analysis_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    if not symbol:
        return _missing_entity_plan("deep_analyze_symbol", "symbol")
    return AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            _step(
                "analysis.deep_symbol",
                _date_args(entities, symbol=symbol),
                "Compose score, feature, level, market, sector, freshness, and lineage context",
                "READ_SCORE",
            )
        ],
        assumptions=["Only persisted warehouse artifacts are authoritative."],
        required_artifacts=[
            "candidate_score",
            "feature_snapshot",
            "canonical_ohlcv",
            "market_regime_snapshot",
            "sector_strength_snapshot",
        ],
    )


def _build_quality_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities) or None
    args = _date_args(entities)
    if symbol:
        args["symbol"] = symbol
    return AssistantPlan(
        intent="review_quality",
        steps=[
            _step(
                "quality.get_status", args, "Review data quality status", "READ_QUALITY"
            )
        ],
        required_artifacts=["canonical_ohlcv"],
    )


def _build_market_regime_plan(entities: dict) -> AssistantPlan:
    return AssistantPlan(
        intent="review_market_regime",
        steps=[
            _step(
                "market.get_regime",
                _date_args(entities),
                "Review persisted market regime research context",
                "READ_FEATURES",
            )
        ],
        required_artifacts=["market_regime_snapshot"],
    )


def _build_sector_strength_plan(entities: dict) -> AssistantPlan:
    args = _date_args(entities)
    if entities.get("top") is not None:
        args["top"] = entities["top"]
    return AssistantPlan(
        intent="review_sector_strength",
        steps=[
            _step(
                "sector.get_strength",
                args,
                "Review persisted sector strength research context",
                "READ_FEATURES",
            )
        ],
        required_artifacts=["sector_strength_snapshot"],
    )


def _build_symbol_sector_alignment_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    if not symbol:
        return _missing_entity_plan("review_symbol_sector_alignment", "symbol")
    return AssistantPlan(
        intent="review_symbol_sector_alignment",
        steps=[
            _step(
                "sector.get_symbol_alignment",
                _date_args(entities, symbol=symbol),
                "Review a symbol's persisted sector alignment",
                "READ_FEATURES",
            )
        ],
        required_artifacts=["symbol_master", "sector_strength_snapshot"],
    )


def _build_watchlist_deep_plan(entities: dict) -> AssistantPlan:
    args = _date_args(entities)
    if entities.get("top") is not None:
        args["top"] = entities["top"]
    return AssistantPlan(
        intent="summarize_watchlist_deep",
        steps=[
            _step(
                "watchlist.summarize_deep",
                args,
                "Summarize candidate classes, setups, sectors, quality, and risks",
                "READ_WATCHLIST",
            )
        ],
        required_artifacts=[
            "daily_watchlist",
            "candidate_score",
            "market_regime_snapshot",
        ],
    )


def _build_shortlist_plan(entities: dict) -> AssistantPlan:
    args = _date_args(entities)
    for key in ("top", "min_score"):
        if entities.get(key) is not None:
            args[key] = entities[key]
    return AssistantPlan(
        intent="generate_shortlist",
        steps=[
            _step(
                "shortlist.generate",
                args,
                "Rank a bounded research shortlist from persisted evidence",
                "READ_WATCHLIST",
            ),
            _step(
                "market.get_regime",
                _date_args(entities),
                "Attach persisted market context to the shortlist review",
                "READ_FEATURES",
            ),
        ],
        assumptions=[
            "The shortlist is research prioritization only, not an execution or allocation list."
        ],
        required_artifacts=[
            "daily_watchlist",
            "candidate_score",
            "sector_strength_snapshot",
            "market_regime_snapshot",
        ],
    )


def _build_scenario_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    if not symbol:
        return _missing_entity_plan("generate_research_scenario", "symbol")
    return AssistantPlan(
        intent="generate_research_scenario",
        steps=[
            _step(
                "scenario.generate_research_plan",
                _date_args(entities, symbol=symbol),
                "Build conditional confirmation, neutral, and invalidation research scenarios",
                "READ_SCORE",
            )
        ],
        assumptions=[
            "Scenario conditions are descriptive research context and never execution instructions."
        ],
        required_artifacts=["candidate_score", "feature_snapshot", "canonical_ohlcv"],
    )


def _build_setup_evidence_plan(entities: dict) -> AssistantPlan:
    setup_type = str(entities.get("setup_type", "")).strip().upper()
    if not setup_type:
        return _missing_entity_plan("review_setup_evidence", "setup_type")
    args = _date_args(entities, setup_type=setup_type)
    if entities.get("horizon_sessions") is not None:
        args["horizon_sessions"] = entities["horizon_sessions"]
    elif entities.get("horizon") is not None:
        args["horizon_sessions"] = entities["horizon"]
    return AssistantPlan(
        intent="review_setup_evidence",
        steps=[
            _step(
                "evidence.get_setup_history",
                args,
                "Review persisted historical outcome evidence for the setup",
                "READ_HISTORY",
            )
        ],
        required_artifacts=["setup_type_performance", "candidate_outcome"],
    )


def _build_lineage_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    if not symbol:
        return _missing_entity_plan("show_lineage", "symbol")
    return AssistantPlan(
        intent="show_lineage",
        steps=[
            _step(
                "lineage.get_symbol_lineage",
                _date_args(entities, symbol=symbol),
                "Show data lineage",
                "READ_LINEAGE",
            )
        ],
        required_artifacts=["candidate_score", "ingestion_run"],
    )


def _build_summarize_plan(entities: dict) -> AssistantPlan:
    return AssistantPlan(
        intent="summarize_watchlist",
        steps=[
            _step(
                "watchlist.scan",
                _date_args(entities),
                "Retrieve candidates for a short summary",
                "READ_WATCHLIST",
            )
        ],
        required_artifacts=["daily_watchlist"],
    )


def _build_note_plan(entities: dict) -> AssistantPlan:
    symbol = _resolve_symbol(entities)
    args: dict[str, Any] = {
        "symbol": symbol,
        "note_text": entities.get("note_text", ""),
    }
    if entities.get("tags"):
        args["tags"] = entities["tags"]
    return AssistantPlan(
        intent="create_research_note",
        steps=[_step("note.create", args, "Persist research note", "WRITE_NOTE")],
    )


def _build_history_plan(entities: dict) -> AssistantPlan:
    return AssistantPlan(
        intent="show_history",
        steps=[
            _step(
                "history.list_sessions",
                {"limit": entities.get("limit", 20)},
                "List recent research sessions",
                "READ_HISTORY",
            )
        ],
    )


def _build_fetch_plan(_entities: dict) -> AssistantPlan:
    return AssistantPlan(
        intent="fetch_data",
        steps=[],
        refusal_reason=(
            "Warehouse data fetches require an explicit manual command or tool path; "
            "the assistant cannot run data.fetch autonomously."
        ),
    )


def _build_sandbox_plan(entities: dict) -> AssistantPlan:
    purpose = str(entities.get("purpose", "offline research calculation")).strip()
    return AssistantPlan(
        intent="sandbox_research_calculation",
        steps=[
            _step(
                "sandbox.run_research_code",
                {"purpose": purpose},
                "Prepare an approval-gated sandbox research calculation",
                "SANDBOX_APPROVAL",
            )
        ],
    )


def _build_refusal_plan(entities: dict) -> AssistantPlan:
    return AssistantPlan(
        intent="unsupported_or_unsafe",
        steps=[],
        refusal_reason=entities.get(
            "reason", "This request is not supported in the research assistant."
        ),
    )


_PLAN_BUILDERS = {
    "scan_candidates": _build_scan_plan,
    "filter_candidates": _build_filter_plan,
    "compare_symbols": _build_compare_plan,
    "explain_symbol": _build_explain_plan,
    "deep_analyze_symbol": _build_deep_analysis_plan,
    "review_quality": _build_quality_plan,
    "review_market_regime": _build_market_regime_plan,
    "review_sector_strength": _build_sector_strength_plan,
    "review_symbol_sector_alignment": _build_symbol_sector_alignment_plan,
    "summarize_watchlist": _build_summarize_plan,
    "summarize_watchlist_deep": _build_watchlist_deep_plan,
    "generate_shortlist": _build_shortlist_plan,
    "generate_research_scenario": _build_scenario_plan,
    "review_setup_evidence": _build_setup_evidence_plan,
    "show_lineage": _build_lineage_plan,
    "create_research_note": _build_note_plan,
    "show_history": _build_history_plan,
    "fetch_data": _build_fetch_plan,
    "sandbox_research_calculation": _build_sandbox_plan,
    "unsupported_or_unsafe": _build_refusal_plan,
}


def _validate_plan(plan: AssistantPlan) -> None:
    if plan.is_refusal():
        return
    for step in plan.steps:
        from vnalpha.assistant.tool_policy import assert_assistant_plan_tool

        assert_assistant_plan_tool(step.tool_name, error_type=PlanValidationError)


class PlanBuilder:
    """Build AssistantPlan instances from classified intents without LLM planning."""

    def build(self, intent_result: IntentResult) -> AssistantPlan:
        builder = _PLAN_BUILDERS.get(intent_result.intent, _build_refusal_plan)
        try:
            plan = builder(intent_result.entities)
        except Exception as exc:
            raise PlanBuildError(
                f"Failed to build plan for intent '{intent_result.intent}': {exc}"
            ) from exc
        _validate_plan(plan)
        return plan

    def preview(self, plan: AssistantPlan) -> str:
        if plan.is_refusal():
            return f"[REFUSED] {plan.refusal_reason}"
        lines = [f"Plan for intent: {plan.intent}", "Steps:"]
        for index, step in enumerate(plan.steps, 1):
            lines.append(
                f"  {index}. {step.tool_name}({step.arguments}) — {step.purpose}"
            )
        if plan.assumptions:
            lines.append(f"Assumptions: {', '.join(plan.assumptions)}")
        return "\n".join(lines)
