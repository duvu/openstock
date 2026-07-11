from __future__ import annotations

import json
from typing import Any

import duckdb

from vnalpha.commands.normalizers import normalize_date
from vnalpha.policy.research_language import assert_research_language
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_evidence import get_setup_history
from vnalpha.tools.research_intelligence_common import (
    RESEARCH_TOOL_VERSION,
    dedupe,
    required_symbol,
    tool_data,
)
from vnalpha.tools.research_symbol import deep_symbol_analysis


def generate_research_scenario(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
    with_evidence: bool = False,
    with_regime: bool = True,
) -> ToolOutput:
    """Generate a conditional scenario map from persisted symbol context."""

    deep = deep_symbol_analysis(conn, symbol=symbol, date=date)
    context = deep.data if isinstance(deep.data, dict) else {}
    normalized_symbol = required_symbol(symbol)
    as_of_date = str(context.get("as_of_date") or normalize_date(date))
    levels = context.get("levels") if isinstance(context.get("levels"), dict) else {}
    technical = (
        context.get("technical_context")
        if isinstance(context.get("technical_context"), dict)
        else {}
    )
    close = technical.get("close")
    resistance = levels.get("resistance_20d") or levels.get("resistance_60d")
    support = levels.get("support_20d") or levels.get("support_60d")
    volume_ratio = technical.get("volume_ratio")
    missing_data = list(context.get("missing_data") or [])
    if close is None:
        missing_data.append("current close")
    if support is None or resistance is None:
        missing_data.append("derived support/resistance levels")

    scenarios = {
        "base_case": {
            "condition": _range_condition(close, support, resistance),
            "evidence_to_watch": [
                "trend and relative-strength persistence",
                "volume participation",
                "data freshness",
            ],
            "risk_context": (
                "The setup remains descriptive until a persisted condition changes."
            ),
            "caveat": "No future outcome is implied.",
        },
        "confirmation_case": {
            "condition": _confirmation_condition(resistance, volume_ratio),
            "evidence_to_watch": [
                "a persisted close beyond the derived range",
                "volume context relative to its recent average",
                "market and sector context when available",
            ],
            "risk_context": (
                "Confirmation quality weakens if participation or data quality "
                "is incomplete."
            ),
            "caveat": "This is a monitoring condition, not an instruction.",
        },
        "failed_confirmation_case": {
            "condition": _failure_condition(support, resistance),
            "evidence_to_watch": [
                "loss of the derived range",
                "weaker relative strength",
                "new risk flags",
            ],
            "risk_context": (
                "A failed condition reduces confidence in the current setup description."
            ),
            "caveat": "Re-run analysis with fresh persisted data.",
        },
        "low_quality_drift_case": {
            "condition": (
                "Evidence remains mixed without a clear persisted confirmation condition."
            ),
            "evidence_to_watch": [
                "stale or partial feature data",
                "low participation",
                "conflicting regime or sector context",
            ],
            "risk_context": "Unclear evidence should lower research priority.",
            "caveat": "No conclusion should be forced from incomplete data.",
        },
    }
    score_context = context.get("score_context") or {}
    evidence = (
        tool_data(
            get_setup_history(
                conn,
                setup_type=score_context.get("setup_type"),
                symbol=normalized_symbol,
                date=as_of_date,
                horizon=20,
            )
        )
        if with_evidence
        else None
    )
    caveats = dedupe(
        [
            *(context.get("caveats") or []),
            "Conditional research scenario only; future confirmation is required.",
            "The scenario map is not an execution instruction.",
        ]
    )
    data = {
        "status": "READY" if not missing_data else "PARTIAL",
        "symbol": normalized_symbol,
        "as_of_date": as_of_date,
        "current_context": {
            "close": close,
            "setup_type": score_context.get("setup_type"),
            "candidate_class": score_context.get("candidate_class"),
            "levels": levels,
        },
        "scenarios": scenarios,
        "monitoring_checklist": [
            "refresh symbol and benchmark data",
            "review quality and lineage",
            "compare current price/volume evidence with derived levels",
            "review market and sector context",
        ],
        "market_context": context.get("market_context") if with_regime else None,
        "historical_evidence": evidence,
        "policy_status": "PASS",
        "artifact_refs": list(context.get("artifact_refs") or []),
        "freshness": context.get("freshness") or {},
        "methodology_version": RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": dedupe(missing_data),
    }
    assert_research_language(json.dumps(data, default=str), require_marker=True)
    return ToolOutput(
        data=data,
        summary=(
            f"Conditional research scenario for {normalized_symbol} on {as_of_date}."
        ),
        warnings=caveats if missing_data else [],
    )


def _range_condition(close: Any, support: Any, resistance: Any) -> str:
    if close is None or support is None or resistance is None:
        return (
            "Persisted range evidence is incomplete; refresh data before "
            "evaluating the base case."
        )
    return (
        f"Persisted close {close} remains between derived support {support} "
        f"and resistance {resistance}."
    )


def _confirmation_condition(resistance: Any, volume_ratio: Any) -> str:
    if resistance is None:
        return (
            "A confirmation condition cannot be derived because resistance "
            "evidence is unavailable."
        )
    participation = (
        f" with volume ratio context {volume_ratio}"
        if volume_ratio is not None
        else " with participation evidence still required"
    )
    return (
        f"A future persisted close beyond derived resistance {resistance}"
        f"{participation}."
    )


def _failure_condition(support: Any, resistance: Any) -> str:
    if support is None and resistance is None:
        return (
            "The current setup loses consistency with newly persisted "
            "price or quality evidence."
        )
    return (
        "A persisted move back below the reviewed range "
        f"(support {support}, resistance {resistance}) or a material "
        "deterioration in quality evidence."
    )


__all__ = ["generate_research_scenario"]
