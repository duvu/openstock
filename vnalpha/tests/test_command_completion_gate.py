"""Completion-gate tests for Phase 5.8 command execution."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.repositories import save_candidate_score


@pytest.fixture
def conn(
    migrated_warehouse_connection: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    return migrated_warehouse_connection


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
                "candidate_class": "STRONG_CANDIDATE"
                if rank == 1
                else "WATCH_CANDIDATE",
                "setup_type": "ACCUMULATION_BASE",
                "trend_score": 0.8,
                "relative_strength_score": 0.7,
                "volume_score": 0.6,
                "base_score": 0.5,
                "breakout_score": 0.4,
                "risk_quality_score": 0.9,
                "risk_flags": flags,
                "rule_outcomes": {},
                "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
                "scoring_policy_version": BASELINE_SCORING_POLICY.version,
                "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
                "scoring_policy_status": (
                    BASELINE_SCORING_POLICY.lifecycle_status.value
                ),
            },
        )
        conn.execute(
            """
            INSERT INTO daily_watchlist
                (date, rank, symbol, score, candidate_class, setup_type,
                 risk_flags_json, lineage_json, scoring_policy_id,
                 scoring_policy_version, scoring_policy_hash, scoring_policy_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)
            """,
            [
                target_date,
                rank,
                symbol,
                score,
                "STRONG_CANDIDATE" if rank == 1 else "WATCH_CANDIDATE",
                "ACCUMULATION_BASE",
                json.dumps(flags),
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
                BASELINE_SCORING_POLICY.payload_hash,
                BASELINE_SCORING_POLICY.lifecycle_status.value,
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
    def test_unexpected_runtime_failure_is_generic_captured_and_persisted(self, conn):
        from unittest.mock import MagicMock, patch

        from vnalpha.commands.executor import CommandExecutor

        private_fragment = "COMMAND_RUNTIME_PRIVATE_51"
        registry = MagicMock()
        registry.execute.side_effect = RuntimeError(
            f"provider password={private_fragment}"
        )
        with patch("vnalpha.observability.errors.capture_exception") as capture:
            result = CommandExecutor(conn, surface="cli", registry=registry).execute(
                "/scan"
            )

        capture.assert_called_once()
        assert result.status == "FAILED"
        assert result.summary == "Command failed. Check logs and retry."
        assert private_fragment not in result.summary
        persisted = conn.execute(
            "SELECT error_json FROM research_session ORDER BY started_at DESC LIMIT 1"
        ).fetchone()[0]
        assert private_fragment not in persisted
        assert "Command failed. Check logs and retry." in persisted
