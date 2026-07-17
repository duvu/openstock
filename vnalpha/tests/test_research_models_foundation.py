from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import duckdb
import pytest

from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    ResearchAnswerAudit,
    ResearchScenarioPlan,
    SectorStrengthSnapshot,
    SetupAnalysis,
    SetupEvidenceSnapshot,
    ShortlistCandidate,
    ShortlistDecisionReport,
    SymbolLevelSnapshot,
)
from vnalpha.research_models.repositories import ResearchModelsRepository
from vnalpha.research_models.validators import ResearchModelValidationError
from vnalpha.warehouse.migrations import run_migrations


def _models() -> tuple[object, ...]:
    observed_at = datetime(2026, 7, 13, tzinfo=timezone.utc)
    common = {
        "as_of_date": date(2026, 7, 10),
        "freshness": "EXACT_DATE",
        "lineage": {"source": "canonical_ohlcv"},
        "methodology_version": "foundation-v1",
        "correlation_id": "corr-foundation-001",
        "quality_status": "COMPLETE",
        "caveats": ("Research only; verify against fresh data.",),
        "created_at": observed_at,
    }
    return (
        MarketRegimeSnapshot(
            market_regime_snapshot_id="regime-001",
            regime_state="CONSTRUCTIVE",
            index_trend="UPTREND",
            index_volatility="NORMAL",
            breadth_summary={"pct_above_ma20": 0.62},
            sector_strength_ref="sector-001",
            **common,
        ),
        SectorStrengthSnapshot(
            sector_strength_snapshot_id="sector-001",
            sector="Technology",
            rank=1,
            relative_performance=0.12,
            rotation_state="LEADING",
            breadth_proxy={"pct_above_ma20": 0.7},
            member_count=12,
            **common,
        ),
        SymbolLevelSnapshot(
            symbol_level_snapshot_id="level-001",
            symbol="FPT",
            support_levels=(100.0,),
            resistance_levels=(110.0,),
            pivot_levels=(105.0,),
            level_strength={"100": "high"},
            source_bar_refs=("bar:FPT:2026-07-10",),
            **common,
        ),
        SetupAnalysis(
            setup_analysis_id="setup-001",
            symbol="FPT",
            setup_type="BASE_BREAKOUT",
            setup_quality="A",
            trend_context="above_ma50",
            momentum_context="positive",
            relative_strength_context="leading",
            volume_context="above_average",
            volatility_context="normal",
            level_snapshot_ref="level-001",
            confidence=0.8,
            **common,
        ),
        ShortlistCandidate(
            shortlist_candidate_id="candidate-001",
            shortlist_run_id="run-001",
            rank=1,
            symbol="FPT",
            setup_type="BASE_BREAKOUT",
            setup_quality="A",
            shortlist_score=0.9,
            why_shortlisted=("Relative strength is positive.",),
            why_restrained=("Confirm with fresh volume.",),
            confirmation_conditions=("Volume expands.",),
            invalidation_conditions=("Falls below support.",),
            risk_context="Gap risk remains.",
            **common,
        ),
        ShortlistDecisionReport(
            shortlist_decision_report_id="decision-report-001",
            shortlist_run_id="run-001",
            requested_limit=5,
            requested_min_score=0.0,
            considered_count=1,
            shortlisted_count=1,
            truncated_to_limit=False,
            artifact_refs=("daily_watchlist:2026-07-10",),
            missing_data=("eligible_watchlist_candidates",),
            validation_signature="sha256:placeholder",
            validation_checks={
                "score_order": {"passed": True, "details": "scores are ordered."},
                "rank_contiguity": {"passed": True, "details": "ranks are contiguous."},
                "duplicate_symbol_exclusion": {
                    "passed": True,
                    "details": "no duplicate symbols.",
                    "symbols": [],
                },
            },
            scoring_policy={
                "version": "shortlist-v1",
                "top": 5,
                "min_score": 0.0,
            },
            **common,
        ),
        ResearchScenarioPlan(
            scenario_plan_id="scenario-001",
            symbol="FPT",
            current_setup="BASE_BREAKOUT",
            key_levels={"support": 100.0, "resistance": 110.0},
            scenario_tree={"if_confirmed": "monitor"},
            confirmation_conditions=("Close remains above 105.",),
            invalidation_conditions=("Close falls below 100.",),
            checklist=("Review volume.",),
            risk_reward_estimate="Context only; not a recommendation.",
            confidence=0.7,
            policy_classification="RESEARCH_ONLY",
            **common,
        ),
        SetupEvidenceSnapshot(
            setup_evidence_snapshot_id="evidence-001",
            setup_type="BASE_BREAKOUT",
            sample_definition="liquid universe",
            horizon="20d",
            sample_size=40,
            forward_return_distribution={"median": 0.03},
            fae_aae_stats={"fae": 0.08, "aae": -0.02},
            outcome_rate=0.6,
            regime_split={"CONSTRUCTIVE": 20},
            small_sample_caveat="Sample remains limited.",
            **common,
        ),
        ResearchAnswerAudit(
            answer_audit_id="audit-001",
            assistant_session_id="assistant-001",
            research_session_id="research-001",
            intent="research.explain",
            tools_used=("analysis.deep_symbol",),
            artifact_refs=("artifact:level-001",),
            dataset_freshness={"as_of_date": "2026-07-10"},
            groundedness_result={"status": "GROUNDED"},
            policy_result={"status": "RESEARCH_ONLY"},
            missing_data=(),
            caveats=("Research only; verify against fresh data.",),
            created_at=observed_at,
            correlation_id="corr-foundation-001",
        ),
    )


def test_research_models_migrations_are_additive_and_idempotent() -> None:
    conn = duckdb.connect(":memory:")

    run_migrations(conn=conn)
    run_migrations(conn=conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert {
        "research_market_regime_snapshot",
        "research_sector_strength_snapshot",
        "research_symbol_level_snapshot",
        "research_setup_analysis",
        "research_shortlist_candidate",
        "research_shortlist_decision_report",
        "research_scenario_plan",
        "research_setup_evidence_snapshot",
        "research_answer_audit",
    } <= tables
    audit_columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'research_answer_audit'"
        ).fetchall()
    }
    assert {"research_session_id", "missing_data_json"} <= audit_columns


def test_repositories_round_trip_all_research_models() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    repository = ResearchModelsRepository(conn)
    models = _models()

    for model in models:
        repository.create(model)
        assert repository.get(type(model), repository.record_id(model)) == model
        assert repository.list(type(model)) == [model]


def test_validators_require_lineage_caveats_and_research_only_metadata() -> None:
    repository = ResearchModelsRepository(duckdb.connect(":memory:"))
    (
        market_regime,
        sector_strength,
        symbol_level,
        setup_analysis,
        candidate,
        report,
        scenario,
        setup_evidence,
        audit,
    ) = _models()
    invalid_lineage = replace(market_regime, lineage={})
    invalid_scenario = replace(scenario, caveats=())
    execution_metadata = replace(symbol_level, lineage={"order": "submit"})

    for model in (invalid_lineage, invalid_scenario, execution_metadata):
        with pytest.raises(ResearchModelValidationError):
            repository.validate(model)
