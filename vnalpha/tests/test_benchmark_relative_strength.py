from __future__ import annotations

import duckdb
import pandas as pd
import pytest
from typer.testing import CliRunner

from vnalpha.cli import app
from vnalpha.data_availability.planner import capture_availability_snapshot
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_availability.relative_strength_checks import (
    get_relative_strength_evidence,
)
from vnalpha.features.build_features import build_features
from vnalpha.scoring.generate_watchlist import score_universe
from vnalpha.tools.research_intelligence import _feature_snapshot
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations

TARGET_DATE = "2026-07-10"


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = in_memory_connection()
    run_migrations(conn=connection)
    connection.execute(
        """
        INSERT INTO symbol_master
            (symbol, exchange, is_active, security_type, lifecycle_status)
        VALUES ('FPT', 'HOSE', TRUE, 'COMMON_EQUITY', 'ACTIVE')
        """
    )
    for symbol, base in (("FPT", 100.0), ("VNINDEX", 1200.0), ("VN30", 1300.0)):
        _insert_bars(connection, symbol, base)
    yield connection
    connection.close()


def _insert_bars(conn: duckdb.DuckDBPyConnection, symbol: str, base: float) -> None:
    dates = pd.date_range(end=TARGET_DATE, periods=80, freq="B")
    conn.executemany(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, quality_status, ingestion_run_id)
        VALUES (?, ?, '1D', ?, ?, ?, ?, 1000.0, 'fixture', 'pass', 'fixture-run')
        """,
        [
            (
                symbol,
                bar_date.date(),
                base + offset,
                base + offset + 1,
                base + offset - 1,
                base + offset,
            )
            for offset, bar_date in enumerate(dates)
        ],
    )


def test_vn30_reference_is_not_written_as_vnindex(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")

    assert conn.execute(
        """
        SELECT benchmark_symbol, horizon_sessions
        FROM relative_strength_snapshot
        WHERE symbol = 'FPT' AND date = ?
        ORDER BY horizon_sessions
        """,
        [TARGET_DATE],
    ).fetchall() == [("VN30", 20), ("VN30", 60)]
    assert conn.execute(
        """
        SELECT rs_20d_vs_vnindex, rs_60d_vs_vnindex
        FROM feature_snapshot WHERE symbol = 'FPT' AND date = ?
        """,
        [TARGET_DATE],
    ).fetchone() == (None, None)


def test_two_benchmarks_for_one_symbol_date_coexist(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VNINDEX")
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")

    assert conn.execute(
        """
        SELECT benchmark_symbol, horizon_sessions
        FROM relative_strength_snapshot
        WHERE symbol = 'FPT' AND date = ?
        ORDER BY benchmark_symbol, horizon_sessions
        """,
        [TARGET_DATE],
    ).fetchall() == [
        ("VN30", 20),
        ("VN30", 60),
        ("VNINDEX", 20),
        ("VNINDEX", 60),
    ]


def test_default_feature_universe_excludes_registered_indexes(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    result = build_features(conn, TARGET_DATE)

    assert result == {"built": 1, "skipped": 0}
    assert conn.execute(
        "SELECT symbol FROM feature_snapshot ORDER BY symbol"
    ).fetchall() == [("FPT",)]


def test_score_uses_selected_benchmark_relative_strength(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")

    assert score_universe(conn, TARGET_DATE, universe=["FPT"]) == 1
    assert conn.execute(
        """
        SELECT relative_strength_score, lineage_json
        FROM candidate_score WHERE symbol = 'FPT' AND date = ?
        """,
        [TARGET_DATE],
    ).fetchone()[0] > 0.9


def test_readiness_requires_both_selected_benchmark_horizons(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")

    assert get_relative_strength_evidence(conn, "FPT", TARGET_DATE).available is True
    conn.execute(
        """
        DELETE FROM relative_strength_snapshot
        WHERE symbol = 'FPT' AND date = ? AND benchmark_symbol = 'VN30'
          AND horizon_sessions = 60
        """,
        [TARGET_DATE],
    )
    assert get_relative_strength_evidence(conn, "FPT", TARGET_DATE).available is False
    snapshot = capture_availability_snapshot(
        conn, "FPT", TARGET_DATE, DataAvailabilityPolicy(auto_sync=False)
    )
    feature = next(
        evidence
        for evidence in snapshot.artifact_evidence
        if evidence.artifact.value == "feature_snapshot"
    )
    assert feature.available is False


def test_data_feature_build_cli_accepts_benchmark_selection() -> None:
    result = CliRunner().invoke(app, ["data", "build", "features", "--help"])

    assert result.exit_code == 0
    assert "--benchmark" in result.output


def test_deep_analysis_feature_context_uses_actual_benchmark_values(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")

    feature = _feature_snapshot(conn, "FPT", TARGET_DATE)
    assert feature is not None
    assert feature["rs_20d_vs_vnindex"] is not None
    assert feature["lineage"]["benchmark_symbol"] == "VN30"
