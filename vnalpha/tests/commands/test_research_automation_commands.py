from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from vnalpha.commands.models import CommandStatus
from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.observability.context import init_run_context, reset_run_context
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def research_connection(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    reset_run_context()
    _ = init_run_context(surface="test", actor="pytest", log_root=tmp_path)
    with in_memory_connection() as conn:
        run_migrations(conn=conn)
        conn.execute(
            "INSERT INTO feature_snapshot "
            "(symbol, date, close, return_20d, rs_20d_vs_vnindex, base_range_30d, "
            "volatility_20d, volume_ratio, feature_data_status, as_of_bar_date, "
            "benchmark_as_of_bar_date, feature_build_version, lineage_json) VALUES "
            "('FPT', DATE '2026-07-01', 100, 0.12, 0.04, 0.10, 0.02, 0.60, "
            "'EXACT_DATE', DATE '2026-07-01', DATE '2026-07-01', 'v1', "
            '\'{"feature_status_contract_version":"feature-data-status-v1"}\'), '
            "('VNM', DATE '2026-07-01', 80, 0.08, 0.01, 0.20, 0.05, 1.10, "
            "'EXACT_DATE', DATE '2026-07-01', DATE '2026-07-01', 'v1', "
            '\'{"feature_status_contract_version":"feature-data-status-v1"}\')'
        )
        start = date(2026, 7, 1)
        for symbol, base in (("FPT", 100.0), ("VNM", 80.0)):
            for offset in range(15):
                trading_date = start + timedelta(days=offset)
                close = base + offset
                conn.execute(
                    "INSERT INTO canonical_ohlcv "
                    "(symbol, time, interval, open, high, low, close, volume, "
                    "selected_provider, quality_status, ingestion_run_id) "
                    "VALUES (?, ?, '1D', ?, ?, ?, ?, 1000, 'FIXTURE', 'pass', 'run-1')",
                    [
                        symbol,
                        trading_date,
                        close - 0.5,
                        close + 1.0,
                        close - 1.0,
                        close,
                    ],
                )
        conn.execute(
            "INSERT INTO candidate_outcome "
            "(symbol, watchlist_date, horizon_sessions, forward_return, "
            "outcome_status, price_basis, benchmark_price_basis, "
            "adjustment_methodology, adjustment_version, action_overlap_status, "
            "scoring_policy_id, scoring_policy_version, scoring_policy_hash, "
            "scoring_policy_status) VALUES "
            "('FPT', DATE '2026-07-01', 20, 0.12, 'COMPLETE', "
            "'RAW_UNADJUSTED', 'RAW_UNADJUSTED', 'NONE', 'raw-unadjusted-v1', "
            "'CLEAR', ?, ?, ?, ?), "
            "('VNM', DATE '2026-07-01', 20, 0.08, 'COMPLETE', "
            "'RAW_UNADJUSTED', 'RAW_UNADJUSTED', 'NONE', 'raw-unadjusted-v1', "
            "'CLEAR', ?, ?, ?, ?)",
            [
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
                BASELINE_SCORING_POLICY.payload_hash,
                BASELINE_SCORING_POLICY.lifecycle_status.value,
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
                BASELINE_SCORING_POLICY.payload_hash,
                BASELINE_SCORING_POLICY.lifecycle_status.value,
            ],
        )
        yield conn
    reset_run_context()


def _execute(text: str, conn: duckdb.DuckDBPyConnection):
    return build_default_registry().execute(
        parse(text), conn=conn, session_id="session-123"
    )


def _stable_experiment_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def test_feature_create_persists_definition_and_reproducibility_artifacts(
    research_connection: duckdb.DuckDBPyConnection,
) -> None:
    result = _execute(
        "/feature create rs_20 = rs_20d_vs_vnindex --universe VN30",
        research_connection,
    )

    assert result.status is CommandStatus.SUCCESS
    row = research_connection.execute(
        "SELECT feature_name, feature_expression, universe FROM research_feature"
    ).fetchone()
    assert row == ("RS_20", "rs_20d_vs_vnindex", "VN30")

    artifact = research_connection.execute(
        "SELECT status, lineage_json, caveats_json, outputs_json FROM research_artifact"
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "created"
    assert json.loads(artifact[1])["definition_source"] == "slash_command"
    assert json.loads(artifact[2])
    outputs = json.loads(artifact[3])
    for key in (
        "manifest",
        "result_json",
        "summary_md",
        "lineage_json",
        "validation_json",
    ):
        assert Path(outputs[key]).is_file()
    assert (
        "research-only"
        in Path(outputs["summary_md"]).read_text(encoding="utf-8").lower()
    )
