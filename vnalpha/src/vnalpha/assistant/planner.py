"""Plan builder: maps IntentResult to AssistantPlan using Phase 5.8 tool allowlist."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from vnalpha.assistant.errors import PlanBuildError, PlanValidationError
from vnalpha.assistant.models import AssistantPlan, IntentResult, ToolPlanStep

if TYPE_CHECKING:
    pass

# Phase 5.8 allowlisted tools for Phase 5.9
TOOL_ALLOWLIST: frozenset[str] = frozenset({
    "watchlist.scan",
    "watchlist.filter",
    "candidate.compare",
    "candidate.explain",
    "quality.get_status",
    "quality.get_many_status",
    "lineage.get_symbol_lineage",
    "note.create",
    "history.list_sessions",
})

def _step(tool: str, args: dict, purpose: str, permission: str) -> ToolPlanStep:
    return ToolPlanStep(
        step_id=str(uuid.uuid4())[:8],
        tool_name=tool,
        arguments=args,
        purpose=purpose,
        required_permission=permission,
    )

# Deterministic plan builders by intent (no LLM needed for most)
def _build_scan_plan(entities: dict) -> AssistantPlan:
    date = entities.get("date")
    universe = entities.get("universe")
    args: dict[str, Any] = {}
    if date:
        args["date"] = date
    if universe:
        args["universe"] = universe
    return AssistantPlan(
        intent="scan_candidates",
        steps=[_step("watchlist.scan", args, "Retrieve ranked research candidates", "READ_WATCHLIST")],
        required_artifacts=["daily_watchlist", "candidate_score"],
    )

def _build_filter_plan(entities: dict) -> AssistantPlan:
    filters = entities.get("filters", {})
    date = entities.get("date")
    args: dict[str, Any] = {"filters": filters}
    if date:
        args["date"] = date
    return AssistantPlan(
        intent="filter_candidates",
        steps=[_step("watchlist.filter", args, "Filter candidates by criteria", "READ_WATCHLIST")],
        required_artifacts=["candidate_score"],
    )

def _build_compare_plan(entities: dict) -> AssistantPlan:
    symbols = entities.get("symbols", [])
    date = entities.get("date")
    args: dict[str, Any] = {"symbols": symbols}
    if date:
        args["date"] = date
    # Use multi-symbol quality tool when comparing 2+ symbols
    quality_tool = "quality.get_many_status" if len(symbols) > 1 else "quality.get_status"
    quality_args: dict[str, Any] = {"symbols": symbols, **({"date": date} if date else {})}
    if quality_tool == "quality.get_status" and symbols:
        quality_args = {"symbol": symbols[0], **({"date": date} if date else {})}
    steps = [
        _step("candidate.compare", args, "Compare candidate scores and evidence", "READ_SCORE"),
        _step(quality_tool, quality_args,
              "Check data quality for each symbol", "READ_QUALITY"),
    ]
    return AssistantPlan(
        intent="compare_symbols",
        steps=steps,
        required_artifacts=["candidate_score", "canonical_ohlcv"],
    )

def _build_explain_plan(entities: dict) -> AssistantPlan:
    symbol = entities.get("symbol", "")
    date = entities.get("date")
    args: dict[str, Any] = {"symbol": symbol}
    if date:
        args["date"] = date
    steps = [
        _step("candidate.explain", args, "Explain candidate score and evidence", "READ_SCORE"),
        _step("lineage.get_symbol_lineage", args, "Retrieve data lineage", "READ_LINEAGE"),
        _step("quality.get_status", {"symbol": symbol, **({"date": date} if date else {})}, "Check data quality status", "READ_QUALITY"),
    ]
    return AssistantPlan(
        intent="explain_symbol",
        steps=steps,
        required_artifacts=["candidate_score", "ingestion_run"],
    )

def _build_quality_plan(entities: dict) -> AssistantPlan:
    symbol = entities.get("symbol")
    args: dict[str, Any] = {}
    if symbol:
        args["symbol"] = symbol
    if entities.get("date"):
        args["date"] = entities["date"]
    return AssistantPlan(
        intent="review_quality",
        steps=[_step("quality.get_status", args, "Review data quality status", "READ_QUALITY")],
        required_artifacts=["canonical_ohlcv"],
    )

def _build_lineage_plan(entities: dict) -> AssistantPlan:
    symbol = entities.get("symbol", "")
    args: dict[str, Any] = {"symbol": symbol}
    if entities.get("date"):
        args["date"] = entities["date"]
    return AssistantPlan(
        intent="show_lineage",
        steps=[_step("lineage.get_symbol_lineage", args, "Show data lineage", "READ_LINEAGE")],
        required_artifacts=["candidate_score", "ingestion_run"],
    )

def _build_summarize_plan(entities: dict) -> AssistantPlan:
    args: dict[str, Any] = {}
    if entities.get("date"):
        args["date"] = entities["date"]
    return AssistantPlan(
        intent="summarize_watchlist",
        steps=[_step("watchlist.scan", args, "Retrieve all candidates for summary", "READ_WATCHLIST")],
        required_artifacts=["daily_watchlist"],
    )

def _build_note_plan(entities: dict) -> AssistantPlan:
    symbol = entities.get("symbol", "")
    text = entities.get("note_text", "")
    tags = entities.get("tags", [])
    args: dict[str, Any] = {"symbol": symbol, "note_text": text}
    if tags:
        args["tags"] = tags
    return AssistantPlan(
        intent="create_research_note",
        steps=[_step("note.create", args, "Persist research note", "WRITE_NOTE")],
        required_artifacts=[],
    )

def _build_history_plan(entities: dict) -> AssistantPlan:
    limit = entities.get("limit", 20)
    return AssistantPlan(
        intent="show_history",
        steps=[_step("history.list_sessions", {"limit": limit}, "List recent research sessions", "READ_HISTORY")],
        required_artifacts=[],
    )

def _build_refusal_plan(entities: dict) -> AssistantPlan:
    reason = entities.get("reason", "This request is not supported in the research assistant.")
    return AssistantPlan(
        intent="unsupported_or_unsafe",
        steps=[],
        refusal_reason=reason,
    )

_PLAN_BUILDERS = {
    "scan_candidates": _build_scan_plan,
    "filter_candidates": _build_filter_plan,
    "compare_symbols": _build_compare_plan,
    "explain_symbol": _build_explain_plan,
    "review_quality": _build_quality_plan,
    "show_lineage": _build_lineage_plan,
    "summarize_watchlist": _build_summarize_plan,
    "create_research_note": _build_note_plan,
    "show_history": _build_history_plan,
    "unsupported_or_unsafe": _build_refusal_plan,
}


def _validate_plan(plan: AssistantPlan) -> None:
    """Raise PlanValidationError if any step uses a non-allowlisted tool."""
    if plan.is_refusal():
        return
    for step in plan.steps:
        if step.tool_name not in TOOL_ALLOWLIST:
            raise PlanValidationError(
                f"Tool '{step.tool_name}' is not in the Phase 5.9 allowlist. "
                f"Allowed tools: {sorted(TOOL_ALLOWLIST)}"
            )


class PlanBuilder:
    """Builds AssistantPlan from IntentResult using deterministic templates."""

    def build(self, intent_result: IntentResult) -> AssistantPlan:
        intent = intent_result.intent
        builder = _PLAN_BUILDERS.get(intent, _build_refusal_plan)
        try:
            plan = builder(intent_result.entities)
        except Exception as exc:
            raise PlanBuildError(f"Failed to build plan for intent '{intent}': {exc}") from exc
        _validate_plan(plan)
        return plan

    def preview(self, plan: AssistantPlan) -> str:
        """Return a human-readable plan preview string."""
        if plan.is_refusal():
            return f"[REFUSED] {plan.refusal_reason}"
        lines = [f"Plan for intent: {plan.intent}", "Steps:"]
        for i, step in enumerate(plan.steps, 1):
            lines.append(f"  {i}. {step.tool_name}({step.arguments}) — {step.purpose}")
        if plan.assumptions:
            lines.append(f"Assumptions: {', '.join(plan.assumptions)}")
        return "\n".join(lines)
