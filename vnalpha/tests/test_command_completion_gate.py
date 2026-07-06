"""Completion-gate tests for Phase 5.8 command execution."""

from __future__ import annotations

import json
from datetime import date

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


def _seed_watchlist(conn, target_date: str) -> None:
    for rank, symbol, score, flags in [
        (1, "FPT", 0.82, ["THIN_VOLUME"]),
        (2, "VNM", 0.55, []),
    ]:
        save_candidate_score(
            conn,
            symbol,
            target_date,
            {
                "score": score,
                "candidate_class": "STRONG_CANDIDATE" if rank == 1 else "WATCH_CANDIDATE",
                "setup_type": "ACCUMULATION_BASE",
                "trend_score": 0.8,
                "relative_strength_score": 0.7,
                "volume_score": 0.6,
                "base_score": 0.5,
                "breakout_score": 0.4,
                "risk_quality_score": 0.9,
                "risk_flags": flags,
                "rule_outcomes": {},
            },
        )
        conn.execute(
            """
            INSERT INTO daily_watchlist
                (date, rank, symbol, score, candidate_class, setup_type, risk_flags_json, lineage_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
            """,
            [
                target_date,
                rank,
                symbol,
                score,
                "STRONG_CANDIDATE" if rank == 1 else "WATCH_CANDIDATE",
                "ACCUMULATION_BASE",
                json.dumps(flags),
            ],
        )


def _latest_research_session(conn) -> dict:
    row = conn.execute(
        """
        SELECT session_id, status, surface, command_name, error_json
        FROM research_session
        ORDER BY started_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    return {
        "session_id": row[0],
        "status": row[1],
        "surface": row[2],
        "command_name": row[3],
        "error_json": row[4],
    }


class TestCommandExecutorCompletion:
    def test_successful_scan_creates_session_and_tool_trace(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        target_date = date.today().isoformat()
        _seed_watchlist(conn, target_date)

        result = CommandExecutor(conn, surface="cli").execute(f"/scan --date {target_date}")

        assert result.status == "SUCCESS"
        session = _latest_research_session(conn)
        assert session["status"] == "SUCCESS"
        assert session["surface"] == "cli"
        assert session["command_name"] == "scan"
        traces = conn.execute(
            "SELECT tool_name, status, trace_parent_type FROM tool_trace WHERE session_id = ?",
            [session["session_id"]],
        ).fetchall()
        assert traces == [("watchlist.scan", "SUCCESS", "command")]

    def test_parse_error_persists_validation_error_session(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        result = CommandExecutor(conn, surface="cli").execute("no leading slash")

        assert result.status == "VALIDATION_ERROR"
        session = _latest_research_session(conn)
        assert session["status"] == "VALIDATION_ERROR"
        assert session["command_name"] is None
        assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0

    def test_unknown_command_persists_validation_error_session(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        result = CommandExecutor(conn, surface="cli").execute("/unknown")

        assert result.status == "VALIDATION_ERROR"
        session = _latest_research_session(conn)
        assert session["status"] == "VALIDATION_ERROR"
        assert session["command_name"] == "unknown"
        assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0

    def test_malformed_filter_is_validation_error_without_tool_trace(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        result = CommandExecutor(conn, surface="cli").execute("/filter score>>0.70")

        assert result.status == "VALIDATION_ERROR"
        assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0

    def test_unsupported_filter_field_is_validation_error_without_tool_trace(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        result = CommandExecutor(conn, surface="cli").execute('/filter raw_sql="drop table candidate_score"')

        assert result.status == "VALIDATION_ERROR"
        assert conn.execute("SELECT COUNT(*) FROM tool_trace").fetchone()[0] == 0

    def test_scan_result_renders_risk_flags_column(self, conn):
        from vnalpha.commands.executor import CommandExecutor

        target_date = date.today().isoformat()
        _seed_watchlist(conn, target_date)

        result = CommandExecutor(conn, surface="cli").execute(f"/scan VN30 --date {target_date}")

        table = result.tables[0]
        assert any(c.name == "risk_flags" for c in table.columns)
        assert any("THIN_VOLUME" in str(row) for row in table.rows)
