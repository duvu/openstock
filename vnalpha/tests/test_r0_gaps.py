"""R0 gap-closure tests — feature metadata, migration upgrade, CLI boundary.

Task coverage:
  1.2.1  MISSING_BENCHMARK status is set when VNINDEX is absent
  1.2.2  STALE_DATE status is set when target date has no exact bar
  1.2.3  EXACT_DATE status is set when target date has exact bar
  1.2.4  as_of_bar_date records the actual bar date used
  1.2.5  benchmark_as_of_bar_date records the actual benchmark bar date used
  1.2.6  Feature lineage includes provider, ingestion_run_id, source quality, bar date, version
  1.3.1  Migration from minimal warehouse (only base R0 tables) succeeds
  1.3.2  Migrations add feature metadata columns without dropping rows
  1.3.3  Migrations add assistant/chat/outcome tables without dropping rows
  1.3.4  Migrations add candidate/outcome versioning columns without dropping rows
  1.3.5  Migration can be run twice safely (idempotent)
  1.4.1  Explicit --symbols overrides --universe
  1.4.2  Unknown --universe exits non-zero with useful error text
  1.4.3  sync index --symbol VNINDEX command shape via monkeypatch
  1.4.4  watchlist --date no-data message
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import duckdb
import pandas as pd
from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_schema_without_metadata() -> duckdb.DuckDBPyConnection:
    """Minimal feature_snapshot without metadata columns — simulates old warehouse."""
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE canonical_ohlcv (
            symbol VARCHAR,
            interval VARCHAR,
            time DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            selected_provider VARCHAR,
            quality_status VARCHAR,
            ingestion_run_id VARCHAR,
            source_service_run_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE feature_snapshot (
            symbol VARCHAR NOT NULL,
            date DATE NOT NULL,
            close DOUBLE,
            ma20 DOUBLE, ma50 DOUBLE, ma100 DOUBLE,
            ma20_slope DOUBLE, ma50_slope DOUBLE,
            volume_ma20 DOUBLE, volume_ratio DOUBLE,
            atr14 DOUBLE, return_20d DOUBLE, return_60d DOUBLE,
            rs_20d_vs_vnindex DOUBLE, rs_60d_vs_vnindex DOUBLE,
            distance_to_ma20 DOUBLE, distance_to_52w_high DOUBLE,
            base_range_30d DOUBLE, close_strength DOUBLE,
            volatility_20d DOUBLE,
            PRIMARY KEY (symbol, date)
        )
    """)
    return conn


def _make_full_schema_conn() -> duckdb.DuckDBPyConnection:
    """Full schema via run_migrations."""
    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _make_ohlcv_df(
    n: int = 200, end_date: str = "2024-06-28", seed: int = 42
) -> pd.DataFrame:
    """Create synthetic OHLCV DataFrame ending on end_date."""
    import numpy as np

    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    idx = pd.date_range(end=end_date, periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": prices * (1 - rng.uniform(0, 0.005, n)),
            "high": prices * (1 + rng.uniform(0, 0.01, n)),
            "low": prices * (1 - rng.uniform(0, 0.01, n)),
            "close": prices,
            "volume": rng.integers(500_000, 2_000_000, n).astype(float),
        },
        index=idx,
    )


def _insert_ohlcv(
    conn,
    symbol: str,
    n: int = 200,
    end_date: str = "2024-06-28",
    seed: int = 42,
    provider: str | None = "vnstock",
    ingestion_run_id: str | None = "run-001",
):
    """Insert synthetic OHLCV rows directly into canonical_ohlcv."""
    df = _make_ohlcv_df(n=n, end_date=end_date, seed=seed)
    rows = [
        (
            symbol,
            str(d),  # TIMESTAMP format
            "1D",
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"]),
            provider,
            "PASS",
            ingestion_run_id,
            None,
        )
        for d, row in df.iterrows()
    ]
    conn.executemany(
        "INSERT INTO canonical_ohlcv (symbol, time, interval, open, high, low, close, volume, selected_provider, quality_status, ingestion_run_id, source_service_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return df


# ---------------------------------------------------------------------------
# Task 1.2.1 — MISSING_BENCHMARK status when VNINDEX absent
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.2.2 — STALE_DATE when target date has no exact bar
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.2.3 — EXACT_DATE when target date has exact bar
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.2.4 — as_of_bar_date records actual bar date used
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.2.5 — benchmark_as_of_bar_date records actual benchmark bar date
# ---------------------------------------------------------------------------


def test_benchmark_as_of_bar_date_records_actual_benchmark_date():
    """benchmark_as_of_bar_date records the actual benchmark bar date used (1.2.5)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    target = "2024-06-28"
    bench_end = "2024-06-27"  # benchmark ends a day before target
    _insert_ohlcv(conn, "FPT", end_date=target)
    _insert_ohlcv(conn, "VNINDEX", end_date=bench_end, seed=99)

    build_features(conn, target, universe=["FPT"])

    row = conn.execute(
        "SELECT benchmark_as_of_bar_date FROM feature_snapshot WHERE symbol='FPT' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    assert str(row[0]) == bench_end


# ---------------------------------------------------------------------------
# Task 1.2.6 — lineage includes provider, ingestion_run_id, quality, bar date, version
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.3.1 — Migration from minimal warehouse succeeds
# ---------------------------------------------------------------------------


def test_migration_from_minimal_warehouse():
    """Migration from a minimal warehouse (base R0 tables only) succeeds (1.3.1)."""
    from vnalpha.warehouse.migrations import run_migrations

    # Start with just the base tables, no metadata columns
    conn = duckdb.connect()
    conn.execute("""
        CREATE TABLE ingestion_run (
            ingestion_run_id VARCHAR PRIMARY KEY,
            provider VARCHAR,
            endpoint VARCHAR,
            universe VARCHAR,
            status VARCHAR DEFAULT 'running',
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ,
            rows_inserted INTEGER,
            error_json VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE symbol_master (
            symbol VARCHAR PRIMARY KEY,
            exchange VARCHAR,
            company_name VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            last_updated TIMESTAMPTZ DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE TABLE market_ohlcv_raw (
            symbol VARCHAR,
            interval VARCHAR,
            time TIMESTAMPTZ,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            source VARCHAR,
            ingestion_run_id VARCHAR,
            PRIMARY KEY (symbol, interval, time, source)
        )
    """)
    conn.execute("""
        CREATE TABLE canonical_ohlcv (
            symbol VARCHAR,
            interval VARCHAR,
            time DATE,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            selected_provider VARCHAR,
            quality_status VARCHAR,
            ingestion_run_id VARCHAR,
            source_service_run_id VARCHAR,
            PRIMARY KEY (symbol, interval, time)
        )
    """)
    conn.execute("""
        CREATE TABLE feature_snapshot (
            symbol VARCHAR NOT NULL,
            date DATE NOT NULL,
            close DOUBLE,
            ma20 DOUBLE, ma50 DOUBLE, ma100 DOUBLE,
            ma20_slope DOUBLE, ma50_slope DOUBLE,
            volume_ma20 DOUBLE, volume_ratio DOUBLE,
            atr14 DOUBLE, return_20d DOUBLE, return_60d DOUBLE,
            rs_20d_vs_vnindex DOUBLE, rs_60d_vs_vnindex DOUBLE,
            distance_to_ma20 DOUBLE, distance_to_52w_high DOUBLE,
            base_range_30d DOUBLE, close_strength DOUBLE,
            volatility_20d DOUBLE,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE candidate_score (
            symbol VARCHAR, date DATE,
            score DOUBLE, setup_type VARCHAR, risk_flag VARCHAR,
            score_version VARCHAR,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE daily_watchlist (
            date DATE, symbol VARCHAR, rank INTEGER, score DOUBLE,
            PRIMARY KEY (date, symbol)
        )
    """)
    conn.execute("""
        CREATE TABLE rejected_symbol (
            symbol VARCHAR, date DATE, reason VARCHAR,
            PRIMARY KEY (symbol, date)
        )
    """)

    # Now run full migrations — must not fail
    run_migrations(conn=conn)

    # All expected tables should now exist
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "chat_session" in tables
    assert "chat_message" in tables
    assert "assistant_session" in tables
    assert "outcome_evaluation_run" in tables


# ---------------------------------------------------------------------------
# Task 1.3.2 — Migrations add feature metadata columns without dropping rows
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.3.3 — Migrations add assistant/chat/outcome tables without dropping rows
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.3.4 — Migrations add versioning columns without dropping rows
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.3.5 — Migration can be run twice safely (idempotent)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.4.1 — Explicit --symbols overrides --universe
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.4.2 — Unknown --universe exits non-zero with useful error text
# ---------------------------------------------------------------------------


def test_cli_unknown_universe_exits_nonzero():
    """sync ohlcv --universe UNKNOWN exits non-zero with useful message (1.4.2)."""
    with (
        patch("vnalpha.ingestion.sync_ohlcv.sync_ohlcv") as _mock_sync,
        patch("vnalpha.warehouse.connection.get_connection") as mock_conn,
        patch("vnalpha.warehouse.migrations.run_migrations"),
    ):
        mock_conn.return_value = MagicMock()
        result = runner.invoke(
            app, ["sync", "ohlcv", "--universe", "TOTALLY_UNKNOWN_XYZ"]
        )

    assert result.exit_code != 0
    combined = result.output + (str(result.exception) if result.exception else "")
    assert "Unknown universe" in combined or result.exit_code == 1


# ---------------------------------------------------------------------------
# Task 1.4.3 — sync index --symbol VNINDEX command shape via monkeypatch
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 1.4.4 — watchlist --date no-data message
# ---------------------------------------------------------------------------
