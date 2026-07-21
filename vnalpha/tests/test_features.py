"""Tests for feature computations using synthetic data."""

import duckdb
import numpy as np
import pandas as pd

from vnalpha.features.price import (
    compute_ma,
)


def make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create synthetic OHLCV DataFrame with DatetimeIndex."""
    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
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


# --- Price features ---


def test_compute_ma():
    df = make_ohlcv(50)
    ma = compute_ma(df["close"], 20)
    assert ma.notna().sum() == 31  # 50 - 20 + 1


# --- Volume features ---


# --- Volatility features ---


# --- Relative strength ---


# --- Integration ---


# --- build_features() DB integration (metadata columns) ---


def _make_conn_with_schema() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection with required tables."""
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
            as_of_bar_date DATE,
            benchmark_as_of_bar_date DATE,
            source_row_count INTEGER,
            benchmark_row_count INTEGER,
            feature_data_status VARCHAR,
            feature_build_version VARCHAR,
            feature_generated_at TIMESTAMPTZ,
            lineage_json VARCHAR,
            PRIMARY KEY (symbol, date)
        )
    """)
    return conn


def _insert_ohlcv(conn, symbol, n=200, end_date="2024-06-28", seed=42):
    """Insert synthetic OHLCV rows for a symbol."""
    df = make_ohlcv(n, seed=seed)
    # Override index to end at end_date
    idx = pd.date_range(end=end_date, periods=n, freq="B")
    df.index = idx
    rows = [
        (
            symbol,
            str(d.date()),
            "1D",
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"],
            None,
            None,
            None,
            None,
        )
        for d, row in df.iterrows()
    ]
    conn.executemany(
        """
        INSERT INTO canonical_ohlcv (
            symbol, time, interval, open, high, low, close, volume,
            selected_provider, quality_status, ingestion_run_id,
            source_service_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return df
