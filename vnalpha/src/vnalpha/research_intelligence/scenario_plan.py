"""Typed research-only scenario-plan artifact contract."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

import duckdb

from vnalpha.research_intelligence.deep_analysis import DeepAnalysisBuilder
from vnalpha.research_intelligence.scenario_policy import (
    RESEARCH_ONLY_DISCLAIMER,
    validate_research_only_language,
)
from vnalpha.warehouse.repositories import (
    get_candidate_score,
    save_research_scenario_plan,
)


class ScenarioBranch(TypedDict):
    """One conditional research branch grounded in observed evidence."""

    condition: str
    evidence_to_watch: list[str]
    risk_context: str
    caveat: str


class ResearchScenarioPlan(TypedDict):
    """Persisted research scenario plan for one symbol and as-of date."""

    scenario_plan_id: str
    symbol: str
    as_of_date: str
    current_setup: dict[str, object]
    key_levels: list[dict[str, object]]
    confirmation_conditions: list[str]
    invalidation_conditions: list[str]
    scenario_tree: dict[str, ScenarioBranch]
    risk_reward_estimate: dict[str, object] | None
    checklist: list[str]
    confidence: float
    caveats: list[str]
    research_only_language: str
    artifact_references: dict[str, object]
    correlation_id: str


class ScenarioPlanBuilder:
    """Build a policy-validated scenario plan from persisted research evidence."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._analysis = DeepAnalysisBuilder(conn)

    def build(
        self,
        symbol: str,
        date: str,
        *,
        with_evidence: bool = False,
        with_regime: bool = False,
        correlation_id: str | None = None,
    ) -> ResearchScenarioPlan:
        """Build, validate, and persist one research-only scenario plan."""
        analysis = self._analysis.build(
            symbol,
            date,
            with_sector=False,
            with_regime=with_regime,
        )
        levels = list(analysis["levels"]["levels"])
        score = get_candidate_score(self._conn, symbol, date)
        caveats = self._caveats(analysis, levels, score, with_evidence)
        confirmation_conditions = self._confirmation_conditions(analysis, levels)
        invalidation_conditions = self._invalidation_conditions(analysis, levels)
        evidence_snapshot = self._evidence_snapshot(score, with_evidence, symbol, date)
        plan: ResearchScenarioPlan = {
            "scenario_plan_id": str(uuid.uuid4()),
            "symbol": symbol,
            "as_of_date": date,
            "current_setup": {
                "trend": analysis["trend"],
                "setup_quality": analysis["setup_quality"],
                "data_freshness": analysis["data_freshness"],
            },
            "key_levels": levels,
            "confirmation_conditions": confirmation_conditions,
            "invalidation_conditions": invalidation_conditions,
            "scenario_tree": self._scenario_tree(
                confirmation_conditions,
                invalidation_conditions,
                caveats,
            ),
            "risk_reward_estimate": self._risk_reward_estimate(levels),
            "checklist": self._checklist(with_evidence, with_regime),
            "confidence": float(analysis["confidence"]),
            "caveats": caveats,
            "research_only_language": RESEARCH_ONLY_DISCLAIMER,
            "artifact_references": {
                "deep_analysis": {
                    "table": "setup_analysis",
                    "symbol": symbol,
                    "date": date,
                },
                "level_snapshot": {
                    "table": "symbol_level_snapshot",
                    "symbol": symbol,
                    "date": date,
                },
                "evidence_snapshot": evidence_snapshot,
            },
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }
        validate_research_only_language(plan)
        save_research_scenario_plan(self._conn, plan)
        return plan

    @staticmethod
    def _caveats(
        analysis: dict[str, object],
        levels: list[dict[str, object]],
        score: dict[str, Any] | None,
        with_evidence: bool,
    ) -> list[str]:
        caveats = [str(value) for value in analysis["risk_caveats"]]
        caveats.extend(str(value) for value in analysis["missing_data"])
        if not levels:
            caveats.append(
                "Key level data is unavailable; conditions remain qualitative research context."
            )
        if with_evidence and score is None:
            caveats.append(
                "Requested candidate-score evidence is unavailable for this as-of date."
            )
        if not with_evidence:
            caveats.append("Candidate-score evidence snapshot was not requested.")
        return list(dict.fromkeys(caveats))

    @staticmethod
    def _confirmation_conditions(
        analysis: dict[str, object], levels: list[dict[str, object]]
    ) -> list[str]:
        resistance = ScenarioPlanBuilder._level_value(levels, "RESISTANCE")
        conditions = [
            "Observe whether subsequent persisted trend and volume evidence remains consistent with the current setup.",
        ]
        if resistance is not None:
            conditions.append(
                f"Observe whether subsequent persisted closes remain above the observed resistance reference ({resistance:.2f})."
            )
        else:
            conditions.append(
                "No observed resistance reference is available; review subsequent persisted level data before updating the scenario."
            )
        if analysis["confidence"] < 1:
            conditions.append(
                "Confirm missing evidence is resolved before relying on the current confidence context."
            )
        return conditions

    @staticmethod
    def _invalidation_conditions(
        analysis: dict[str, object], levels: list[dict[str, object]]
    ) -> list[str]:
        support = ScenarioPlanBuilder._level_value(levels, "SUPPORT")
        trend = analysis["trend"]["state"]
        conditions = [
            f"Reassess the research context if the observed trend state changes from {trend}.",
        ]
        if support is not None:
            conditions.append(
                f"Reassess the research context if subsequent persisted closes fall below the observed support reference ({support:.2f})."
            )
        else:
            conditions.append(
                "No observed support reference is available; treat the scenario as lower-confidence research context."
            )
        return conditions

    @staticmethod
    def _scenario_tree(
        confirmation_conditions: list[str],
        invalidation_conditions: list[str],
        caveats: list[str],
    ) -> dict[str, ScenarioBranch]:
        caveat = (
            caveats[0]
            if caveats
            else "Future evidence may change this research context."
        )
        return {
            "base_case": {
                "condition": "The observed trend and level context remains broadly consistent.",
                "evidence_to_watch": confirmation_conditions[:1],
                "risk_context": "Confidence reflects available persisted evidence only.",
                "caveat": caveat,
            },
            "confirmation_case": {
                "condition": confirmation_conditions[0],
                "evidence_to_watch": confirmation_conditions,
                "risk_context": "Confirmation depends on future persisted observations.",
                "caveat": caveat,
            },
            "failed_confirmation_case": {
                "condition": invalidation_conditions[0],
                "evidence_to_watch": invalidation_conditions,
                "risk_context": "Observed setup quality may no longer support the prior context.",
                "caveat": caveat,
            },
            "low_quality_drift_case": {
                "condition": "Data freshness, lineage, or level coverage becomes incomplete.",
                "evidence_to_watch": ["Data freshness", "Lineage", "Level coverage"],
                "risk_context": "Incomplete evidence reduces confidence in the scenario context.",
                "caveat": caveat,
            },
        }

    @staticmethod
    def _risk_reward_estimate(
        levels: list[dict[str, object]],
    ) -> dict[str, object] | None:
        support = ScenarioPlanBuilder._level_value(levels, "SUPPORT")
        resistance = ScenarioPlanBuilder._level_value(levels, "RESISTANCE")
        reference_close = ScenarioPlanBuilder._level_value(levels, "REFERENCE_CLOSE")
        if (
            support is None
            or resistance is None
            or reference_close is None
            or not support < reference_close < resistance
        ):
            return None
        downside = reference_close - support
        upside = resistance - reference_close
        return {
            "label": "rough level-grounded research estimate",
            "observed_upside_to_downside_ratio": round(upside / downside, 2),
            "caveat": "This is not an execution instruction and requires future confirmation.",
        }

    @staticmethod
    def _checklist(with_evidence: bool, with_regime: bool) -> list[str]:
        checklist = [
            "Review data freshness and lineage on the next persisted update.",
            "Review observed trend, volume, and level context.",
            "Review caveats before updating the scenario.",
        ]
        if with_evidence:
            checklist.append("Review candidate-score evidence and risk flags.")
        if with_regime:
            checklist.append("Review persisted market regime context.")
        return checklist

    @staticmethod
    def _evidence_snapshot(
        score: dict[str, Any] | None,
        requested: bool,
        symbol: str,
        date: str,
    ) -> dict[str, object]:
        if not requested:
            return {"status": "not_requested", "symbol": symbol, "date": date}
        if score is None:
            return {"status": "unavailable", "symbol": symbol, "date": date}
        return {
            "status": "available",
            "symbol": symbol,
            "date": date,
            "score": score.get("score"),
            "evidence": score.get("evidence_json", {}),
            "risk_flags": score.get("risk_flags_json", []),
            "lineage": score.get("lineage_json", {}),
        }

    @staticmethod
    def _level_value(levels: list[dict[str, object]], level_type: str) -> float | None:
        for level in levels:
            if level.get("type") != level_type:
                continue
            value = level.get("value")
            if isinstance(value, (int, float)):
                return float(value)
        return None
