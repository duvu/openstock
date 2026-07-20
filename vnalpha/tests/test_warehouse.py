"""Tests for the DuckDB warehouse."""

import pytest

from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    get_symbols_active,
    get_watchlist,
    insert_raw_ohlcv,
    upsert_symbol,
)


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
        "disclosure_raw_occurrence",
        "symbol_event",
        "ranking_evaluation_manifest",
        "ranking_evaluation_strategy",
        "ranking_replay",
        "ranking_replay_period",
        "ranking_policy_decision",
    }
    assert expected == names


def test_ingestion_run_lifecycle(conn):
    run_id = create_ingestion_run(
        conn, "vnstock-service", "/v1/reference/symbols", "VN30"
    )
    assert len(run_id) == 36  # uuid4
    rows = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?", [run_id]
    ).fetchall()
    assert rows[0][0] == "RUNNING"
    finish_ingestion_run(conn, run_id, "SUCCESS")
    rows = conn.execute(
        "SELECT status FROM ingestion_run WHERE ingestion_run_id = ?", [run_id]
    ).fetchall()
    assert rows[0][0] == "SUCCESS"


def test_upsert_symbol(conn):
    upsert_symbol(conn, "FPT", exchange="HOSE", name="FPT Corp")
    rows = conn.execute("SELECT symbol, exchange, name FROM symbol_master").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("FPT", "HOSE", "FPT Corp")
    # Upsert again with updated name
    upsert_symbol(conn, "FPT", exchange="HOSE", name="FPT Corporation")
    rows = conn.execute(
        "SELECT name FROM symbol_master WHERE symbol = 'FPT'"
    ).fetchall()
    assert rows[0][0] == "FPT Corporation"


def test_get_active_symbols(conn):
    upsert_symbol(conn, "FPT")
    upsert_symbol(conn, "VNM")
    symbols = get_symbols_active(conn)
    assert "FPT" in symbols
    assert "VNM" in symbols


def test_insert_raw_ohlcv(conn):
    # Need an ingestion run first
    run_id = create_ingestion_run(conn, "vnstock-service", "/v1/equity/ohlcv")
    records = [
        {
            "time": "2024-01-02",
            "interval": "1D",
            "open": 90.0,
            "high": 92.0,
            "low": 89.0,
            "close": 91.5,
            "volume": 1000000.0,
        },
    ]
    inserted = insert_raw_ohlcv(
        conn, run_id, "FPT", records, "kbs", "pass", "2024-01-02T09:00:00"
    )
    assert inserted == 1


def test_insert_raw_ohlcv_reports_only_rows_stored(conn):
    run_id = create_ingestion_run(conn, "vnstock-service", "/v1/equity/ohlcv")
    record = {
        "time": "2024-01-02",
        "interval": "1D",
        "open": 90.0,
        "high": 92.0,
        "low": 89.0,
        "close": 91.5,
        "volume": 1000000.0,
    }

    inserted = insert_raw_ohlcv(conn, run_id, "FPT", [record, record], "KBS")

    assert inserted == 1
    assert conn.execute("SELECT count(*) FROM market_ohlcv_raw").fetchone() == (1,)


def test_run_migrations_idempotent(conn):
    """Migrations can be run multiple times safely."""
    run_migrations(conn=conn)  # second run
    tables = conn.execute("SHOW TABLES").fetchall()
    assert (
        len(tables) == 74
    )  # + ranking_evaluation_manifest + ranking_evaluation_strategy (issue #261)


def test_get_watchlist_empty(conn):
    result = get_watchlist(conn, "2024-01-02")
    assert result == []


# ── Rejected-symbol date semantics tests ─────────────────────────────────────


def test_build_canonical_rejected_uses_bar_date(conn):
    """Invalid OHLCV bars should be rejected with their actual bar date, not job run date."""
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

    run_id = create_ingestion_run(conn, "test-service", "/test")
    # Insert a raw row with invalid close (close <= 0 triggers rejection)
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
        (ingestion_run_id, symbol, time, interval, open, high, low, close, volume, provider, fetched_at)
        VALUES (?, 'BADFPT', '2024-03-15', '1D', 10.0, 11.0, 9.0, -1.0, 1000.0, 'KBS', current_timestamp)
    """,
        [run_id],
    )
    build_canonical_ohlcv(conn, interval="1D", symbol="BADFPT")

    rows = conn.execute(
        "SELECT symbol, date, stage, reason, provider FROM rejected_symbol WHERE symbol = 'BADFPT'"
    ).fetchall()
    assert len(rows) >= 1, "Expected at least one rejected_symbol row"
    _, rej_date, _, reason, _ = rows[0]
    # The rejected date must be the bar date (2024-03-15), NOT today's date
    assert str(rej_date) == "2024-03-15", (
        f"rejected_symbol.date should be the bar date '2024-03-15', got '{rej_date}'"
    )
    assert reason == "INVALID_OHLCV"


def test_build_canonical_rejected_carries_provider(conn):
    """Rejected rows should include the provider that sourced the bad bar."""
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv

    run_id = create_ingestion_run(conn, "test-service", "/test")
    # Insert a raw row where high < low to trigger rejection
    conn.execute(
        """
        INSERT INTO market_ohlcv_raw
        (ingestion_run_id, symbol, time, interval, open, high, low, close, volume, provider, fetched_at)
        VALUES (?, 'PROVTEST', '2024-04-01', '1D', 10.0, 5.0, 11.0, 10.0, 1000.0, 'VCI', current_timestamp)
    """,
        [run_id],
    )
    build_canonical_ohlcv(conn, interval="1D", symbol="PROVTEST")

    row = conn.execute(
        "SELECT provider FROM rejected_symbol WHERE symbol = 'PROVTEST'"
    ).fetchone()
    assert row is not None
    assert row[0] == "VCI"
