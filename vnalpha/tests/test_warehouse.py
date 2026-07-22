"""Tests for the DuckDB warehouse."""

import os
import threading

import duckdb
import pytest

from vnalpha.core.config import AppConfig, WarehouseConfig
from vnalpha.warehouse import connection
from vnalpha.warehouse.connection import (
    WarehouseOpenError,
    WarehouseOpenFailureKind,
    in_memory_connection,
    read_connection,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.transaction import WarehouseTransactionRollbackOnlyError
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


def test_configured_warehouse_connection_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    configured_path = tmp_path / "configured" / "warehouse.duckdb"

    monkeypatch.setattr(
        connection,
        "get_config",
        lambda: AppConfig(warehouse=WarehouseConfig(path=configured_path)),
    )

    cases = [
        (duckdb.IOException("Could not set lock on file"), "busy"),
        (duckdb.PermissionException("private path"), "permission"),
        (duckdb.InvalidInputException("unsupported database schema"), "schema"),
        (duckdb.IOException("configured warehouse unavailable"), "unavailable"),
    ]
    for cause, expected_kind in cases:
        attempts: list[tuple[str, bool]] = []

        def unavailable(
            database: str,
            *,
            read_only: bool = False,
            recorded_attempts: list[tuple[str, bool]] = attempts,
            open_cause: duckdb.Error = cause,
        ) -> None:
            recorded_attempts.append((database, read_only))
            raise open_cause

        monkeypatch.setattr(connection.duckdb, "connect", unavailable)
        with pytest.raises(connection.WarehouseOpenError) as raised:
            connection.get_connection()
        assert raised.value.kind.value == expected_kind
        assert attempts == [(str(configured_path), True)]


def test_warehouse_writers_are_exclusive_and_release_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    approved_parent = tmp_path / "approved"
    approved_parent.mkdir(mode=0o770)
    os.chmod(approved_parent, 0o770)
    warehouse_path = approved_parent / "warehouse.duckdb"
    coordinator = WarehouseWriteCoordinator(path=warehouse_path)
    with coordinator.transaction() as database:
        database.execute("CREATE TABLE writes(value INTEGER)")

    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first_writer() -> None:
        with coordinator.transaction() as database:
            database.execute("INSERT INTO writes VALUES (1)")
            first_entered.set()
            assert release_first.wait(timeout=2)

    def second_writer() -> None:
        with coordinator.transaction() as database:
            database.execute("INSERT INTO writes VALUES (2)")
            second_entered.set()

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    assert not second_entered.wait(timeout=0.1)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert not first.is_alive()
    assert not second.is_alive()

    with coordinator.transaction() as database:
        database.execute("INSERT INTO writes VALUES (3)")

    with read_connection(warehouse_path) as database:
        assert database.execute(
            "SELECT value FROM writes ORDER BY value"
        ).fetchall() == [
            (1,),
            (2,),
            (3,),
        ]

    exposed_parent = tmp_path / "exposed"
    exposed_parent.mkdir(mode=0o777)
    os.chmod(exposed_parent, 0o777)
    with pytest.raises(WarehouseOpenError) as raised:
        with WarehouseWriteCoordinator(
            path=exposed_parent / "warehouse.duckdb"
        ).transaction():
            pass
    assert raised.value.kind is WarehouseOpenFailureKind.PERMISSION
    assert not (exposed_parent / ".vnalpha-locks").exists()
    assert not (exposed_parent / "warehouse.duckdb").exists()


def test_nested_warehouse_failure_rolls_back_outer_transaction(tmp_path) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    coordinator = WarehouseWriteCoordinator(path=warehouse_path)
    with coordinator.transaction() as database:
        database.execute("CREATE TABLE writes(value INTEGER)")

    with pytest.raises(WarehouseTransactionRollbackOnlyError):
        with coordinator.transaction() as database:
            database.execute("INSERT INTO writes VALUES (1)")
            try:
                with coordinator.transaction() as nested:
                    nested.execute("INSERT INTO writes VALUES (2)")
                    raise RuntimeError("force nested rollback")
            except RuntimeError:
                database.execute("INSERT INTO writes VALUES (3)")

    with read_connection(warehouse_path) as database:
        assert database.execute("SELECT value FROM writes").fetchall() == []


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
        "maintenance_run_job",
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
