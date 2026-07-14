from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from vnalpha.observability.context import get_correlation_id
from vnalpha.research_models.models import (
    ResearchScenarioPlan,
    SetupEvidenceSnapshot,
    SymbolLevelSnapshot,
)

_METHODOLOGY_VERSION = "research-scenario-plan-engine/v1"
_RESEARCH_ONLY_CAVEAT = "Research-only conditional context; not a recommendation."


@dataclass(frozen=True, slots=True)
class ScenarioPlanBuild:
    scenario_plan: ResearchScenarioPlan
    level_snapshot: SymbolLevelSnapshot
    setup_evidence_snapshot: SetupEvidenceSnapshot
    payload: dict[str, Any]


class ScenarioPlanBuilder:
    def build(
        self,
        *,
        symbol: str,
        as_of_date: date,
        candidate: Mapping[str, Any],
        feature: Mapping[str, Any],
        levels: Mapping[str, Any],
        quality: Mapping[str, Any],
        artifact_refs: Sequence[str],
        freshness: Mapping[str, Any],
        analysis_caveats: Sequence[str],
        missing_data: Sequence[str],
        setup_evidence: Mapping[str, Any],
        setup_evidence_caveats: Sequence[str],
    ) -> ScenarioPlanBuild:
        correlation_id = _correlation_id()
        current_setup = {
            "candidate_class": candidate.get("candidate_class"),
            "setup_type": candidate.get("setup_type"),
            "score": candidate.get("score"),
            "risk_flags": _risk_flags(candidate.get("risk_flags_json")),
        }
        key_levels = _key_levels(levels, feature)
        scenario_missing_data = list(dict.fromkeys(missing_data))
        scenario_missing_data.extend(
            item
            for item in setup_evidence.get("missing_data", [])
            if isinstance(item, str) and item not in scenario_missing_data
        )
        scenario_caveats = _caveats(
            [*analysis_caveats, *setup_evidence_caveats], key_levels
        )
        confirmation_conditions = _confirmation_conditions(key_levels)
        invalidation_conditions = _invalidation_conditions(key_levels)
        risk_reward_context = _risk_reward_context(key_levels)
        scenario_tree = _scenario_tree(
            confirmation_conditions,
            invalidation_conditions,
            risk_reward_context,
            scenario_missing_data,
            quality,
        )
        risk_reward_estimate = _risk_reward_estimate(risk_reward_context)
        level_snapshot = self._level_snapshot(
            symbol=symbol,
            as_of_date=as_of_date,
            levels=key_levels,
            artifact_refs=artifact_refs,
            freshness=freshness,
            correlation_id=correlation_id,
            caveats=scenario_caveats,
        )
        setup_evidence_snapshot = self._setup_evidence_snapshot(
            setup_type=str(candidate.get("setup_type") or "UNCLASSIFIED"),
            as_of_date=as_of_date,
            setup_evidence=setup_evidence,
            caveats=setup_evidence_caveats,
            correlation_id=correlation_id,
        )
        scenario_plan_id = _artifact_id("scenario", symbol, as_of_date)
        lineage = {
            "deep_symbol_analysis_ref": f"analysis.deep_symbol:{symbol}:{as_of_date}",
            "symbol_level_snapshot_ref": level_snapshot.symbol_level_snapshot_id,
            "setup_evidence_snapshot_ref": (
                setup_evidence_snapshot.setup_evidence_snapshot_id
            ),
            "correlation_id": correlation_id,
        }
        quality_status = "PARTIAL" if scenario_missing_data else "AVAILABLE"
        scenario_plan = ResearchScenarioPlan(
            scenario_plan_id=scenario_plan_id,
            symbol=symbol,
            as_of_date=as_of_date,
            current_setup=str(current_setup.get("setup_type") or "UNCLASSIFIED"),
            key_levels={
                key: value for key, value in key_levels.items() if value is not None
            },
            scenario_tree=scenario_tree,
            confirmation_conditions=tuple(confirmation_conditions),
            invalidation_conditions=tuple(invalidation_conditions),
            checklist=_checklist(),
            risk_reward_estimate=risk_reward_estimate,
            confidence=_confidence(current_setup.get("score"), scenario_missing_data),
            caveats=tuple(scenario_caveats),
            policy_classification="RESEARCH_ONLY",
            freshness=_json(freshness),
            lineage=lineage,
            methodology_version=_METHODOLOGY_VERSION,
            correlation_id=correlation_id,
            quality_status=quality_status,
            created_at=datetime.now(timezone.utc),
        )
        derived_refs = [
            *artifact_refs,
            f"research_symbol_level_snapshot:{level_snapshot.symbol_level_snapshot_id}",
            f"research_setup_evidence_snapshot:{setup_evidence_snapshot.setup_evidence_snapshot_id}",
            f"research_scenario_plan:{scenario_plan_id}",
        ]
        payload = {
            "tool": "scenario.generate_research_plan",
            "available": True,
            "scenario_plan_id": scenario_plan_id,
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "current_setup": current_setup,
            "key_levels": key_levels,
            "scenario_tree": scenario_tree,
            "scenarios": list(scenario_tree.values()),
            "confirmation_conditions": confirmation_conditions,
            "invalidation_conditions": invalidation_conditions,
            "risk_reward_context": risk_reward_context,
            "risk_reward_estimate": risk_reward_estimate,
            "checklist": list(scenario_plan.checklist),
            "confidence": scenario_plan.confidence,
            "artifact_refs": list(dict.fromkeys(derived_refs)),
            "freshness": dict(freshness),
            "lineage": lineage,
            "missing_data": scenario_missing_data,
            "caveats": scenario_caveats,
            "policy_classification": "RESEARCH_ONLY",
            "policy": {
                "mode": "research_only",
                "disclaimer": _RESEARCH_ONLY_CAVEAT,
            },
        }
        return ScenarioPlanBuild(
            scenario_plan=scenario_plan,
            level_snapshot=level_snapshot,
            setup_evidence_snapshot=setup_evidence_snapshot,
            payload=payload,
        )

    def _level_snapshot(
        self,
        *,
        symbol: str,
        as_of_date: date,
        levels: Mapping[str, float | None],
        artifact_refs: Sequence[str],
        freshness: Mapping[str, Any],
        correlation_id: str,
        caveats: Sequence[str],
    ) -> SymbolLevelSnapshot:
        source_ref = next(
            (ref for ref in artifact_refs if ref.startswith("canonical_ohlcv:")),
            f"canonical_ohlcv:{symbol}:through:{as_of_date}",
        )
        return SymbolLevelSnapshot(
            symbol_level_snapshot_id=_artifact_id("levels", symbol, as_of_date),
            symbol=symbol,
            as_of_date=as_of_date,
            support_levels=_numbers(levels, ("support_20d", "low_60d")),
            resistance_levels=_numbers(levels, ("resistance_20d", "high_60d")),
            pivot_levels=_numbers(levels, ("ma20", "ma50")),
            level_strength={
                "support_20d": "20-session persisted low",
                "resistance_20d": "20-session persisted high",
            },
            source_bar_refs=(source_ref,),
            freshness=_json(freshness),
            lineage={
                "deep_symbol_analysis_ref": f"analysis.deep_symbol:{symbol}:{as_of_date}"
            },
            methodology_version=_METHODOLOGY_VERSION,
            correlation_id=correlation_id,
            quality_status="AVAILABLE"
            if levels.get("latest_close") is not None
            else "PARTIAL",
            caveats=tuple(caveats),
            created_at=datetime.now(timezone.utc),
        )

    def _setup_evidence_snapshot(
        self,
        *,
        setup_type: str,
        as_of_date: date,
        setup_evidence: Mapping[str, Any],
        caveats: Sequence[str],
        correlation_id: str,
    ) -> SetupEvidenceSnapshot:
        evidence = setup_evidence.get("evidence")
        evidence = evidence if isinstance(evidence, Mapping) else {}
        sample_size = _integer(evidence.get("candidate_count"))
        available = bool(setup_evidence.get("available"))
        return SetupEvidenceSnapshot(
            setup_evidence_snapshot_id=_artifact_id(
                "evidence", setup_type.lower(), as_of_date
            ),
            setup_type=setup_type,
            as_of_date=as_of_date,
            sample_definition="Persisted setup-type outcome evidence.",
            horizon=f"{setup_evidence.get('horizon_sessions') or 20} sessions",
            sample_size=sample_size,
            forward_return_distribution=_numeric_mapping(
                evidence,
                ("avg_forward_return", "median_forward_return", "avg_excess_return"),
            ),
            fae_aae_stats=_numeric_mapping(evidence, ("avg_max_drawdown",)),
            outcome_rate=_number_or_none(evidence.get("hit_rate")),
            regime_split={},
            small_sample_caveat=(
                str(caveats[0])
                if caveats
                else "No persisted outcome evidence is available."
            ),
            caveats=tuple(dict.fromkeys([*caveats, _RESEARCH_ONLY_CAVEAT])),
            freshness=_json(setup_evidence.get("freshness") or {}),
            lineage={
                "setup_history_ref": _setup_history_ref(setup_evidence, setup_type),
                "availability": "available" if available else "unavailable",
            },
            methodology_version=_METHODOLOGY_VERSION,
            correlation_id=correlation_id,
            quality_status="AVAILABLE" if available else "PARTIAL",
            created_at=datetime.now(timezone.utc),
        )


def _key_levels(
    levels: Mapping[str, Any], feature: Mapping[str, Any]
) -> dict[str, float | None]:
    latest_close = levels.get("latest_close")
    if not _is_number(latest_close):
        latest_close = feature.get("close")
    return {
        "latest_close": _number_or_none(latest_close),
        "support_20d": _number_or_none(levels.get("support_20d")),
        "resistance_20d": _number_or_none(levels.get("resistance_20d")),
        "ma20": _number_or_none(feature.get("ma20")),
        "ma50": _number_or_none(feature.get("ma50")),
        "atr14": _number_or_none(feature.get("atr14")),
        "low_60d": _number_or_none(levels.get("low_60d")),
        "high_60d": _number_or_none(levels.get("high_60d")),
    }


def _confirmation_conditions(levels: Mapping[str, float | None]) -> list[str]:
    conditions = [
        _condition("price_above_ma20", levels, "latest_close", "ma20", ">="),
        _condition(
            "price_tests_resistance",
            levels,
            "latest_close",
            "resistance_20d",
            ">=",
        ),
        "Persisted volume and market context remain consistent with setup evidence.",
    ]
    return [condition for condition in conditions if condition]


def _invalidation_conditions(levels: Mapping[str, float | None]) -> list[str]:
    conditions = [
        _condition("price_below_support", levels, "latest_close", "support_20d", "<"),
        _condition("price_below_ma50", levels, "latest_close", "ma50", "<"),
        "A material deterioration in persisted market or sector quality weakens the thesis.",
    ]
    return [condition for condition in conditions if condition]


def _scenario_tree(
    confirmation_conditions: Sequence[str],
    invalidation_conditions: Sequence[str],
    risk_reward_context: Mapping[str, float | str | None],
    missing_data: Sequence[str],
    quality: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    quality_status = str(quality.get("status") or "unavailable")
    coverage = ", ".join(missing_data) or "no missing prerequisite artifacts"
    risk_context = str(risk_reward_context["basis"])
    return {
        "base_case": {
            "name": "base_case",
            "condition": "Persisted setup evidence remains internally consistent.",
            "conditions": [
                "Persisted setup evidence remains internally consistent.",
                "No invalidation condition is present in the bounded snapshot.",
            ],
            "evidence_to_watch": "Persisted level, market, sector, and setup-evidence refreshes.",
            "risk_context": risk_context,
            "caveat": _RESEARCH_ONLY_CAVEAT,
            "interpretation": "Continue research review as fresh persisted artifacts become available.",
        },
        "confirmation_case": {
            "name": "confirmation_case",
            "condition": confirmation_conditions[0]
            if confirmation_conditions
            else "Confirmation evidence is unavailable.",
            "conditions": list(confirmation_conditions),
            "evidence_to_watch": "Persisted price-level and volume-context confirmation conditions.",
            "risk_context": risk_context,
            "caveat": _RESEARCH_ONLY_CAVEAT,
            "interpretation": "Confirmation supports continued research review of the persisted setup.",
        },
        "failed_confirmation_case": {
            "name": "failed_confirmation_case",
            "condition": "Confirmation conditions do not persist.",
            "conditions": [
                "Confirmation conditions do not persist.",
                *invalidation_conditions,
            ],
            "evidence_to_watch": "Persisted support, moving-average, market, and sector deterioration evidence.",
            "risk_context": risk_context,
            "caveat": "The bounded snapshot can change when new persisted artifacts arrive.",
            "interpretation": "The persisted setup is not supported by the current bounded evidence.",
        },
        "low_quality_drift_case": {
            "name": "low_quality_drift_case",
            "condition": f"Prerequisite coverage is incomplete: {coverage}.",
            "conditions": [
                f"Data quality status is {quality_status}; missing artifacts: {coverage}.",
                "Refresh persisted artifacts before relying on this scenario.",
            ],
            "evidence_to_watch": "Freshness, quality status, and the currently missing persisted artifacts.",
            "risk_context": f"Coverage state: {coverage}.",
            "caveat": "Incomplete or stale artifacts reduce confidence in this research context.",
            "interpretation": "Treat the scenario as incomplete research context until data quality improves.",
        },
    }


def _risk_reward_context(
    levels: Mapping[str, float | None],
) -> dict[str, float | str | None]:
    latest_close = levels.get("latest_close")
    support = levels.get("support_20d")
    resistance = levels.get("resistance_20d")
    reward_distance = (
        round(resistance - latest_close, 6)
        if latest_close is not None and resistance is not None
        else None
    )
    risk_distance = (
        round(latest_close - support, 6)
        if latest_close is not None and support is not None
        else None
    )
    ratio = (
        round(reward_distance / risk_distance, 4)
        if reward_distance is not None
        and risk_distance is not None
        and reward_distance > 0
        and risk_distance > 0
        else None
    )
    return {
        "risk_distance": risk_distance,
        "reward_distance": reward_distance,
        "reward_risk_ratio": ratio,
        "basis": "20-session persisted support and resistance distance; descriptive only.",
    }


def _risk_reward_estimate(context: Mapping[str, float | str | None]) -> str:
    ratio = context.get("reward_risk_ratio")
    if isinstance(ratio, float):
        return (
            f"Rough descriptive reward-to-risk ratio: {ratio:.4f}; it depends on "
            "future confirmation, is not a recommendation, and is not an execution instruction."
        )
    return (
        "No numeric rough reward-to-risk estimate is available; it depends on future "
        "confirmation, is not a recommendation, and is not an execution instruction."
    )


def _checklist() -> tuple[str, ...]:
    return (
        "Confirm data freshness and quality before relying on the scenario.",
        "Review market regime and sector alignment caveats.",
        "Re-run the scenario after material price or data changes.",
    )


def _caveats(
    analysis_caveats: Sequence[str], levels: Mapping[str, float | None]
) -> list[str]:
    caveats = [str(caveat) for caveat in analysis_caveats if str(caveat).strip()]
    if not any(value is not None for value in levels.values()):
        caveats.append(
            "Key levels are unavailable because persisted level inputs are incomplete."
        )
    caveats.append(_RESEARCH_ONLY_CAVEAT)
    return list(dict.fromkeys(caveats))


def _condition(
    name: str,
    levels: Mapping[str, float | None],
    left_key: str,
    right_key: str,
    operator: str,
) -> str | None:
    right = levels.get(right_key)
    if right is None:
        return None
    left = levels.get(left_key)
    left_text = f"{left:.4f}" if left is not None else "latest close"
    return f"{name}: {left_text} {operator} {right:.4f}"


def _confidence(score: Any, missing_data: Sequence[str]) -> float:
    score_value = _number_or_none(score)
    baseline = score_value if score_value is not None else 0.0
    penalty = min(0.5, 0.1 * len(missing_data))
    return round(max(0.0, min(1.0, baseline - penalty)), 4)


def _setup_history_ref(setup_evidence: Mapping[str, Any], setup_type: str) -> str:
    refs = setup_evidence.get("artifact_refs")
    if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes, bytearray)):
        for ref in refs:
            if isinstance(ref, str) and ref.startswith("setup_type_performance:"):
                return ref
    return f"setup_type_performance:{setup_type}:unavailable"


def _numbers(
    values: Mapping[str, float | None], keys: Sequence[str]
) -> tuple[float, ...]:
    return tuple(value for key in keys if (value := values.get(key)) is not None)


def _numeric_mapping(
    values: Mapping[str, Any], keys: Sequence[str]
) -> dict[str, float]:
    return {
        key: number
        for key in keys
        if (number := _number_or_none(values.get(key))) is not None
    }


def _risk_flags(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value else []
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value]
    return []


def _number_or_none(value: Any) -> float | None:
    return float(value) if _is_number(value) else None


def _integer(value: Any) -> int:
    number = _number_or_none(value)
    return int(number) if number is not None else 0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def _artifact_id(prefix: str, scope: str, as_of_date: date) -> str:
    return f"{prefix}-{scope.lower()}-{as_of_date:%Y%m%d}-{uuid4().hex[:12]}"


def _correlation_id() -> str:
    correlation_id = get_correlation_id()
    return correlation_id if correlation_id != "unset" else f"scenario-{uuid4().hex}"


__all__ = ["ScenarioPlanBuild", "ScenarioPlanBuilder"]
