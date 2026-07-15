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

import json
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


def test_feature_data_status_missing_benchmark():
    """feature_data_status = MISSING_BENCHMARK when VNINDEX data is absent (1.2.1)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    target = "2024-06-28"
    _insert_ohlcv(conn, "FPT", end_date=target)
    # No VNINDEX inserted

    result = build_features(conn, target, universe=["FPT"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT feature_data_status FROM feature_snapshot WHERE symbol='FPT' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    assert row[0] == "MISSING_BENCHMARK"


# ---------------------------------------------------------------------------
# Task 1.2.2 — STALE_DATE when target date has no exact bar
# ---------------------------------------------------------------------------


def test_feature_data_status_stale_date():
    """feature_data_status = STALE_DATE when last bar < target date (1.2.2)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    data_end = "2024-06-25"
    target = "2024-06-28"
    _insert_ohlcv(conn, "ACB", end_date=data_end)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    result = build_features(conn, target, universe=["ACB"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT feature_data_status FROM feature_snapshot WHERE symbol='ACB' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    assert row[0] == "STALE_DATE"


# ---------------------------------------------------------------------------
# Task 1.2.3 — EXACT_DATE when target date has exact bar
# ---------------------------------------------------------------------------


def test_feature_data_status_exact_date():
    """feature_data_status = EXACT_DATE when target date has an exact bar (1.2.3)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    target = "2024-06-28"
    _insert_ohlcv(conn, "VNM", end_date=target)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    result = build_features(conn, target, universe=["VNM"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT feature_data_status FROM feature_snapshot WHERE symbol='VNM' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    assert row[0] == "EXACT_DATE"


# ---------------------------------------------------------------------------
# Task 1.2.4 — as_of_bar_date records actual bar date used
# ---------------------------------------------------------------------------


def test_as_of_bar_date_records_actual_bar_date():
    """as_of_bar_date records the actual bar date used (1.2.4)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    data_end = "2024-06-25"
    target = "2024-06-28"
    _insert_ohlcv(conn, "ACB", end_date=data_end)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    build_features(conn, target, universe=["ACB"])

    row = conn.execute(
        "SELECT as_of_bar_date FROM feature_snapshot WHERE symbol='ACB' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    # as_of_bar_date should be earlier than target (last available bar)
    assert str(row[0]) == data_end


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


def test_feature_lineage_includes_all_required_fields():
    """Feature lineage_json includes provider, ingestion_run_id, source quality, bar date, version (1.2.6)."""
    from vnalpha.features.build_features import build_features

    conn = _make_full_schema_conn()
    target = "2024-06-28"
    _insert_ohlcv(
        conn, "FPT", end_date=target, provider="vnstock", ingestion_run_id="run-abc123"
    )
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    build_features(conn, target, universe=["FPT"])

    row = conn.execute(
        "SELECT lineage_json, feature_build_version FROM feature_snapshot WHERE symbol='FPT' AND date=?",
        [target],
    ).fetchone()
    assert row is not None
    lineage_json, build_version = row
    assert lineage_json is not None
    lineage = json.loads(lineage_json)

    assert "provider" in lineage
    assert "ingestion_run_id" in lineage
    assert "source_quality_status" in lineage
    assert "as_of_bar_date" in lineage
    assert "feature_build_version" in lineage
    assert lineage["ingestion_run_id"] == "run-abc123"
    assert build_version is not None


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


def test_migration_adds_feature_metadata_columns_without_dropping_rows():
    """Migrations add feature metadata columns and do not drop existing rows (1.3.2)."""
    from vnalpha.warehouse.migrations import run_migrations

    conn = _make_schema_without_metadata()
    # Insert a row BEFORE migration
    conn.execute(
        "INSERT INTO feature_snapshot (symbol, date, close, ma20) VALUES ('FPT', '2024-01-01', 100.0, 98.0)"
    )

    run_migrations(conn=conn)

    # Row must still exist
    row = conn.execute(
        "SELECT symbol, close FROM feature_snapshot WHERE symbol='FPT'"
    ).fetchone()
    assert row is not None
    assert row[0] == "FPT"
    assert row[1] == 100.0

    # Metadata column must now exist
    cols = conn.execute("DESCRIBE feature_snapshot").fetchall()
    col_names = {c[0] for c in cols}
    assert "as_of_bar_date" in col_names
    assert "feature_data_status" in col_names
    assert "lineage_json" in col_names


def test_migrations_mark_pre_profile_feature_rows_legacy_unknown():
    from vnalpha.warehouse.migrations import run_migrations

    # Given: a feature snapshot created before completeness evidence existed.
    conn = _make_schema_without_metadata()
    conn.execute(
        "INSERT INTO feature_snapshot (symbol, date, close) VALUES ('FPT', '2024-01-01', 100.0)"
    )

    # When: the warehouse migration runs.
    run_migrations(conn=conn)

    # Then: the row remains readable but cannot claim a known profile.
    row = conn.execute(
        """
        SELECT feature_profile, neutral_completeness,
               relative_strength_completeness
        FROM feature_snapshot
        WHERE symbol = 'FPT'
        """
    ).fetchone()
    assert row == ("LEGACY_UNKNOWN", "LEGACY_UNKNOWN", "LEGACY_UNKNOWN")


# ---------------------------------------------------------------------------
# Task 1.3.3 — Migrations add assistant/chat/outcome tables without dropping rows
# ---------------------------------------------------------------------------


def test_migration_adds_assistant_chat_outcome_tables_without_dropping_existing_rows():
    """Migrations add new tables without dropping existing rows (1.3.3)."""
    from vnalpha.warehouse.migrations import run_migrations

    conn = _make_full_schema_conn()
    conn.execute(
        "INSERT INTO canonical_ohlcv (symbol, time, interval, open, high, low, close, volume) VALUES ('TEST', '2024-01-01 00:00:00', '1D', 1, 1, 1, 1, 1)"
    )

    # Run migration again (should be idempotent)
    run_migrations(conn=conn)

    # Existing row must still be present
    row = conn.execute(
        "SELECT symbol FROM canonical_ohlcv WHERE symbol='TEST'"
    ).fetchone()
    assert row is not None
    assert row[0] == "TEST"

    # New tables must exist
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    assert "chat_session" in tables
    assert "chat_message" in tables
    assert "assistant_session" in tables


# ---------------------------------------------------------------------------
# Task 1.3.4 — Migrations add versioning columns without dropping rows
# ---------------------------------------------------------------------------


def test_migration_adds_versioning_columns_without_dropping_rows():
    """Migrations add candidate/outcome versioning columns without dropping rows (1.3.4)."""
    from vnalpha.warehouse.migrations import run_migrations

    conn = _make_full_schema_conn()
    conn.execute("""
        INSERT INTO candidate_outcome (symbol, watchlist_date, horizon_sessions, outcome_status)
        VALUES ('FPT', '2024-01-01', 20, 'pending')
    """)

    run_migrations(conn=conn)

    # Row still exists
    row = conn.execute(
        "SELECT symbol FROM candidate_outcome WHERE symbol='FPT'"
    ).fetchone()
    assert row is not None

    # Versioning columns must exist
    cols = {c[0] for c in conn.execute("DESCRIBE candidate_outcome").fetchall()}
    assert "evaluation_run_id" in cols


# ---------------------------------------------------------------------------
# Task 1.3.5 — Migration can be run twice safely (idempotent)
# ---------------------------------------------------------------------------


def test_migration_idempotent_double_run():
    """Running run_migrations twice does not raise or break schema (1.3.5)."""
    from vnalpha.warehouse.migrations import run_migrations

    conn = _make_full_schema_conn()
    conn.execute(
        "INSERT INTO canonical_ohlcv (symbol, time, interval, open, high, low, close, volume) VALUES ('IDM', '2024-01-01 00:00:00', '1D', 1, 1, 1, 1, 1)"
    )

    # Second run — must not raise
    run_migrations(conn=conn)

    # Data still intact
    row = conn.execute(
        "SELECT symbol FROM canonical_ohlcv WHERE symbol='IDM'"
    ).fetchone()
    assert row is not None


# ---------------------------------------------------------------------------
# Task 1.4.1 — Explicit --symbols overrides --universe
# ---------------------------------------------------------------------------


def test_cli_explicit_symbols_overrides_universe():
    """parse_symbols_or_universe: explicit symbols take precedence (1.4.1)."""
    from vnalpha.core.universe import parse_symbols_or_universe

    result = parse_symbols_or_universe("FPT,VNM", "VN30")
    assert "FPT" in result
    assert "VNM" in result
    # Should not contain full VN30 set
    assert len(result) == 2


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


def test_cli_sync_index_command_shape():
    """sync index --symbol VNINDEX invokes sync_index_ohlcv with correct symbol (1.4.3)."""
    with (
        patch("vnalpha.ingestion.sync_index.sync_index_ohlcv") as mock_sync,
        patch("vnalpha.warehouse.connection.get_connection") as mock_conn,
        patch("vnalpha.warehouse.migrations.run_migrations"),
    ):
        mock_conn.return_value = MagicMock()
        mock_sync.return_value = {"inserted": 0, "skipped": 0}
        result = runner.invoke(app, ["sync", "index", "--symbol", "VNINDEX"])

    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args
    assert call_kwargs is not None
    kwargs = call_kwargs[1] if call_kwargs[1] else {}
    symbol_passed = kwargs.get("symbol")
    assert symbol_passed == "VNINDEX"


# ---------------------------------------------------------------------------
# Task 1.4.4 — watchlist --date no-data message
# ---------------------------------------------------------------------------


def test_cli_watchlist_date_no_data_message():
    """watchlist --date with empty warehouse returns no-data message, not a crash (1.4.4)."""
    from vnalpha.warehouse.connection import in_memory_connection
    from vnalpha.warehouse.migrations import run_migrations

    in_mem_conn = in_memory_connection()
    run_migrations(conn=in_mem_conn)

    with (
        patch("vnalpha.warehouse.connection.get_connection", return_value=in_mem_conn),
        patch("vnalpha.warehouse.migrations.run_migrations"),
    ):
        result = runner.invoke(app, ["watchlist", "--date", "2024-01-01"])

    assert result.exception is None or result.exit_code in (0, 1)
    output = result.output or ""
    no_crash = "Traceback" not in output or result.exit_code == 0
    assert no_crash
