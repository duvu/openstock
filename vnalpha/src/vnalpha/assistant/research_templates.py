"""Intent-specific synthesis contracts and deterministic fallback answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
from vnalpha.assistant.research_intelligence_intents import (
    POLICY_SENSITIVE_RESEARCH_INTENTS,
    RESEARCH_INTELLIGENCE_INTENTS,
)

_RESEARCH_ONLY_CAVEAT = (
    "Research-only context based on persisted artifacts; not a recommendation or "
    "an instruction to place an order."
)
_CAVEAT_FIRST_INTENTS: Final[frozenset[str]] = frozenset(
    {"review_market_regime", "review_sector_strength"}
)


@dataclass(frozen=True, slots=True)
class ResearchTemplate:
    required_fields: tuple[str, ...]
    allowed_wording: tuple[str, ...]
    required_caveats: tuple[str, ...]
    missing_data_rule: str


RESEARCH_TEMPLATES: Final[dict[str, ResearchTemplate]] = {
    "deep_analyze_symbol": ResearchTemplate(
        required_fields=(
            "symbol",
            "as_of_date",
            "candidate",
            "feature_context",
            "levels",
            "freshness",
            "lineage",
        ),
        allowed_wording=("persisted context", "screening evidence", "research review"),
        required_caveats=("missing artifacts", "data freshness", "research-only"),
        missing_data_rule=(
            "List every unavailable score, feature, price, market, or sector artifact."
        ),
    ),
    "review_market_regime": ResearchTemplate(
        required_fields=("snapshot", "freshness", "lineage", "quality"),
        allowed_wording=("persisted regime", "descriptive context"),
        required_caveats=("coverage", "freshness", "not a forecast"),
        missing_data_rule=(
            "State when no persisted market-regime snapshot is available."
        ),
    ),
    "review_sector_strength": ResearchTemplate(
        required_fields=("snapshots", "freshness", "lineage", "quality"),
        allowed_wording=("persisted ranking", "sector context"),
        required_caveats=("metadata coverage", "freshness", "research-only"),
        missing_data_rule=("State when sector metadata or snapshots are unavailable."),
    ),
    "summarize_watchlist_deep": ResearchTemplate(
        required_fields=(
            "watchlist_size",
            "candidate_class_distribution",
            "setup_distribution",
            "sector_distribution",
            "risk_flag_distribution",
        ),
        allowed_wording=("watchlist structure", "research focus"),
        required_caveats=("data quality", "missing candidates", "research-only"),
        missing_data_rule=(
            "State when the persisted watchlist is empty or unavailable."
        ),
    ),
    "generate_shortlist": ResearchTemplate(
        required_fields=("shortlist", "methodology", "freshness", "caveats"),
        allowed_wording=(
            "research shortlist",
            "prioritization",
            "requires confirmation",
        ),
        required_caveats=("not an execution list", "risk flags", "research-only"),
        missing_data_rule="State when no eligible persisted candidates exist.",
    ),
    "generate_research_scenario": ResearchTemplate(
        required_fields=(
            "current_setup",
            "key_levels",
            "scenarios",
            "checklist",
        ),
        allowed_wording=(
            "base case",
            "confirmation",
            "failed confirmation",
            "low quality drift",
            "conditional",
        ),
        required_caveats=("not a recommendation", "data freshness", "research-only"),
        missing_data_rule=(
            "State when levels or prerequisite artifacts are unavailable."
        ),
    ),
    "review_setup_evidence": ResearchTemplate(
        required_fields=("setup_type", "horizon_sessions", "evidence", "lineage"),
        allowed_wording=("historical persisted evidence", "sample size"),
        required_caveats=("sample size", "historical outcomes", "not predictive"),
        missing_data_rule=("State when no setup-outcome evidence exists."),
    ),
}


def research_prompt_fragment(intent: str) -> str | None:
    """Return intent-specific constraints for the synthesizer system prompt."""

    template = RESEARCH_TEMPLATES.get(intent)
    if template is None:
        return None
    sensitive = (
        "This intent requires an explicit research-only disclaimer. "
        if intent in POLICY_SENSITIVE_RESEARCH_INTENTS
        else ""
    )
    return "\n".join(
        [
            f"Research intent: {intent}",
            "Required payload fields: " + ", ".join(template.required_fields),
            "Allowed framing: " + ", ".join(template.allowed_wording),
            "Required caveats: " + ", ".join(template.required_caveats),
            "Missing-data rule: " + template.missing_data_rule,
            sensitive
            + "Name deterministic tool sources in grounded_source_refs and basis.",
        ]
    )


def build_deterministic_research_answer(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
    *,
    reasons: list[str] | None = None,
) -> AssistantAnswer:
    """Build a fail-closed answer directly from structured tool payloads."""

    payloads = _payloads(plan, tool_outputs)
    missing = _collect_list(payloads, "missing_data")
    caveats = _collect_list(payloads, "caveats")
    source_refs = _source_refs(plan, payloads)
    summary = _summary_for_intent(plan.intent, payloads)
    if missing:
        summary = (
            "Caveat: missing persisted artifacts: "
            + ", ".join(missing)
            + ". "
            + summary
        )
    elif plan.intent in _CAVEAT_FIRST_INTENTS and caveats:
        summary = "Caveat: persisted context includes limitations. " + summary
    tool_names = [step.tool_name for step in plan.steps]
    basis = "Deterministic tools: " + ", ".join(tool_names or ["none"])
    price_bases = tuple(
        dict.fromkeys(
            str(payload["price_basis"])
            for payload in payloads
            if payload.get("price_basis")
        )
    )
    if price_bases:
        basis += "; Price basis: " + ", ".join(price_bases)
    risk_parts = [*caveats, *(reasons or []), _RESEARCH_ONLY_CAVEAT]
    risks = " ".join(dict.fromkeys(item for item in risk_parts if item))
    return AssistantAnswer(
        summary=summary,
        basis=basis,
        risks_caveats=risks,
        tool_trace_summary=(
            f"Executed {len(plan.steps)} deterministic research tool(s): "
            + ", ".join(tool_names)
        ),
        missing_data=missing,
        grounded_source_refs=source_refs,
        research_metadata={
            "intent": plan.intent,
            "fallback_used": True,
            "policy_mode": "research_only",
        },
    )


def is_research_intent(intent: str) -> bool:
    return intent in RESEARCH_INTELLIGENCE_INTENTS


def _payloads(
    plan: AssistantPlan,
    tool_outputs: dict[str, Any],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for step in plan.steps:
        output = tool_outputs.get(step.step_id)
        if not isinstance(output, dict):
            continue
        data = output.get("data", output)
        if isinstance(data, dict):
            payloads.append(data)
    return payloads


def _collect_list(payloads: list[dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for payload in payloads:
        raw = payload.get(field, [])
        if isinstance(raw, (list, tuple)):
            values.extend(str(item) for item in raw if item)
    return list(dict.fromkeys(values))


def _source_refs(
    plan: AssistantPlan,
    payloads: list[dict[str, Any]],
) -> list[str]:
    refs = [f"tool:{step.tool_name}:{step.step_id}" for step in plan.steps]
    refs.extend(_collect_list(payloads, "artifact_refs"))
    return list(dict.fromkeys(refs))


def _primary_payload(intent: str, payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the payload that actually carries this intent's summary fields.

    ``deep_analyze_symbol`` prepends a ``data.ensure_current_symbol``
    provisioning step ahead of ``analysis.deep_symbol``. That provisioning
    payload has no ``candidate``/``as_of_date`` fields, so naively using
    ``payloads[0]`` always rendered "score=None, class=None" even when the
    analysis payload right behind it was fully populated.
    """
    if intent == "deep_analyze_symbol":
        for payload in payloads:
            if "candidate" in payload:
                return payload
    return payloads[0] if payloads else {}


def _summary_for_intent(intent: str, payloads: list[dict[str, Any]]) -> str:
    primary = _primary_payload(intent, payloads)
    if intent == "deep_analyze_symbol":
        status = primary.get("status")
        if status in {"ACCEPTED", "PENDING", "UNAVAILABLE", "FAILED"}:
            return f"Current-symbol research status: {status}."
        candidate = primary.get("candidate") or {}
        return (
            f"{primary.get('symbol', 'Symbol')} as of "
            f"{primary.get('as_of_date') or 'unknown'}: "
            f"score={candidate.get('score')}, "
            f"class={candidate.get('candidate_class')}, "
            f"setup={candidate.get('setup_type')}."
        )
    if intent == "summarize_watchlist_deep":
        return (
            f"Persisted watchlist as of {primary.get('as_of_date') or 'unknown'} "
            f"contains {primary.get('watchlist_size', 0)} candidate(s) across the "
            "reported setups and sectors."
        )
    if intent == "generate_shortlist":
        symbols = [
            str(item.get("symbol"))
            for item in primary.get("shortlist", [])
            if isinstance(item, dict) and item.get("symbol")
        ]
        return (
            "Research shortlist: "
            + (", ".join(symbols) if symbols else "no eligible symbols")
            + "."
        )
    if intent == "generate_research_scenario":
        return (
            f"Conditional research scenario for {primary.get('symbol', 'the symbol')} "
            f"as of {primary.get('as_of_date') or 'unknown'} includes base, "
            "confirmation, failed-confirmation, and low-quality-drift branches."
        )
    if intent == "review_setup_evidence":
        evidence = primary.get("evidence") or {}
        return (
            f"Historical persisted evidence for "
            f"{primary.get('setup_type', 'the setup')} at "
            f"{primary.get('horizon_sessions')} sessions uses a sample of "
            f"{evidence.get('candidate_count', 0)} outcome(s)."
        )
    if intent == "review_market_regime":
        snapshot = primary.get("snapshot") or {}
        return f"Persisted market regime: {snapshot.get('regime', 'unavailable')}."
    if intent == "review_sector_strength":
        snapshots = primary.get("snapshots", [])
        return (
            "Persisted sector context contains "
            f"{len(snapshots)} ranked sector snapshot(s)."
        )
    return "Persisted research context was assembled from deterministic tools."
