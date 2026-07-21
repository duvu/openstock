"""Tests for the DuckDB warehouse."""

import duckdb
import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


def test_configured_warehouse_connection_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from vnalpha.core.config import AppConfig, WarehouseConfig
    from vnalpha.warehouse import connection

    configured_path = tmp_path / "configured" / "warehouse.duckdb"
    attempts: list[tuple[str, bool]] = []

    def unavailable(database: str, *, read_only: bool = False):
        attempts.append((database, read_only))
        raise duckdb.IOException("configured warehouse unavailable")

    monkeypatch.setattr(
        connection,
        "get_config",
        lambda: AppConfig(warehouse=WarehouseConfig(path=configured_path)),
    )
    monkeypatch.setattr(connection.duckdb, "connect", unavailable)

    with pytest.raises(connection.WarehouseOpenError) as raised:
        connection.get_connection()

    assert raised.value.kind is connection.WarehouseOpenFailureKind.UNAVAILABLE
    assert attempts == [(str(configured_path), True)]


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def test_all_tables_created(conn):
    tables = conn.execute("SHOW TABLES").fetchall()
    names = {t[0] for t in tables}
    expected = {
        "ingestion_run",
        "symbol_master",
        "symbol_source_snapshot",
        "symbol_source_membership",
        "reference_membership_snapshot",
        "reference_membership_member",
        "symbol_classification_history",
        "market_ohlcv_raw",
        "canonical_ohlcv",
        "ohlcv_gap_observation",
        "feature_snapshot",
        "benchmark_definition",
        "relative_strength_snapshot",
        "candidate_score",
        "daily_watchlist",
        "rejected_symbol",
        "ohlcv_quarantine",
        "corporate_action_raw_evidence",
        "corporate_action",
        "corporate_action_source_link",
        "corporate_action_quarantine",
        "corporate_action_affected_range",
        "research_session",
        "tool_trace",
        "research_note",
        "assistant_session",
        "llm_trace",
        "prepared_assistant_turn",
        "research_answer_audit",
        "sandbox_approval",
        "sandbox_job",
        "outcome_evaluation_run",
        "candidate_outcome",
        "watchlist_outcome",
        "score_bucket_performance",
        "setup_type_performance",
        "risk_flag_performance",
        "chat_session",
        "chat_message",
        "market_regime_snapshot",
        "sector_strength_snapshot",
        "research_artifact",
        "research_experiment",
        "research_feature",
        "research_hypothesis",
        "research_pattern_scan",
        "research_offline_event_study",
        "research_market_regime_snapshot",
        "research_sector_strength_snapshot",
        "research_symbol_level_snapshot",
        "research_setup_analysis",
        "research_shortlist_candidate",
        "research_shortlist_decision_report",
        "research_scenario_plan",
        "research_setup_evidence_snapshot",
        "scoring_policy_active_pointer",
        "scoring_policy_active_pointer_audit",
        "scoring_policy_decision",
        "memory_event",
        "memory_claim",
        "memory_document",
        "memory_compaction_run",
        "group_context_snapshot",
        "maintenance_run",
        "maintenance_stage_run",
        "fundamental_fact",
        "valuation_snapshot",
        "valuation_snapshot_revision",
        "share_count_fact",
        "disclosure_raw_occurrence",
        "symbol_event",
        "adjusted_ohlcv",
        "adjustment_factor",
        "canonical_selection_audit",
        "ranking_evaluation_manifest",
        "ranking_evaluation_strategy",
        "ranking_evaluation_manifest_v2",
        "ranking_evaluation_strategy_v2",
        "ranking_replay",
        "ranking_replay_period",
        "ranking_replay_v2",
        "ranking_replay_period_v2",
        "ranking_policy_decision",
    }
    assert expected == names


# ── Rejected-symbol date semantics tests ─────────────────────────────────────
