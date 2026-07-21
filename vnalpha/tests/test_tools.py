"""Tests for Local Tool Registry safety (Task 3.5) and tools module (Tasks 3.1-3.4)."""

from __future__ import annotations

import duckdb

from vnalpha.tools.models import (
    ToolOutput,
    ToolPermission,
    ToolSpec,
)


def _make_spec(name: str, permission: ToolPermission) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name}", permission=permission)


def _noop(**kwargs) -> ToolOutput:
    return ToolOutput(data=None, summary="ok")


class TestToolModels:
    def test_tool_permission_values(self):
        """All Phase 5.8 allowed permissions are present."""
        allowed = {p.value for p in ToolPermission}
        assert "READ_WATCHLIST" in allowed
        assert "READ_FEATURES" in allowed
        assert "READ_SCORE" in allowed
        assert "READ_QUALITY" in allowed
        assert "READ_LINEAGE" in allowed
        assert "WRITE_NOTE" in allowed
        assert "READ_HISTORY" in allowed


# ── Quality tool: historical (as-of-date) lookup tests ──────────────────────


def _make_quality_conn() -> duckdb.DuckDBPyConnection:
    """In-memory DB with canonical_ohlcv + rejected_symbol + daily_watchlist."""
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE canonical_ohlcv (
            symbol VARCHAR, time DATE, interval VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            selected_provider VARCHAR, quality_status VARCHAR,
            ingestion_run_id VARCHAR, source_service_run_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE rejected_symbol (
            symbol VARCHAR, date DATE, stage VARCHAR, reason VARCHAR,
            details_json VARCHAR, ingestion_run_id VARCHAR,
            created_at TIMESTAMPTZ DEFAULT current_timestamp
        )
    """)
    conn.execute("""
        CREATE TABLE daily_watchlist (
            date DATE, rank INTEGER, symbol VARCHAR, score DOUBLE,
            candidate_class VARCHAR, setup_type VARCHAR,
            risk_flags_json VARCHAR, lineage_json VARCHAR,
            created_at TIMESTAMPTZ DEFAULT current_timestamp
        )
    """)
    return conn


def _insert_ohlcv_rows(conn, symbol, dates, provider="KBS", quality="PASS"):
    rows = [
        (
            symbol,
            d,
            "1D",
            100.0,
            102.0,
            99.0,
            101.0,
            1000.0,
            provider,
            quality,
            None,
            None,
        )
        for d in dates
    ]
    conn.executemany(
        "INSERT INTO canonical_ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
