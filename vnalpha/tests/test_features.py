"""Tests for feature computations using synthetic data."""

import duckdb
import numpy as np
import pandas as pd

from vnalpha.features.price import (
    compute_close_strength,
    compute_distance_to_ma,
    compute_ma,
    compute_ma_slope,
    compute_price_features,
    compute_return,
)
from vnalpha.features.relative_strength import (
    compute_relative_strength,
    compute_relative_strength_features,
)
from vnalpha.features.volatility import compute_atr, compute_volatility
from vnalpha.features.volume import compute_volume_ma, compute_volume_ratio


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


def test_compute_ma_slope_reasonable():
    df = make_ohlcv(100)
    ma20 = compute_ma(df["close"], 20)
    slope = compute_ma_slope(ma20)
    # Should have some non-NaN values
    assert slope.notna().sum() > 0


def test_distance_to_ma_direction():
    df = make_ohlcv(50)
    ma20 = compute_ma(df["close"], 20)
    dist = compute_distance_to_ma(df["close"], ma20)
    # Close > MA → positive distance; Close < MA → negative
    above = df["close"] > ma20
    assert (dist[above].dropna() > 0).all()
    assert (dist[~above].dropna() <= 0).all()


def test_return_20d():
    df = make_ohlcv(100)
    ret = compute_return(df["close"], 20)
    # First 20 should be NaN
    assert ret.iloc[:20].isna().all()
    assert ret.iloc[20:].notna().all()


def test_close_strength_bounds():
    df = make_ohlcv(100)
    cs = compute_close_strength(df["close"], df["high"], df["low"])
    valid = cs.dropna()
    assert (valid >= 0).all()
    assert (valid <= 1).all()


def test_compute_price_features_columns():
    df = make_ohlcv(200)
    result = compute_price_features(df)
    for col in [
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
        "distance_to_ma20",
        "return_20d",
        "return_60d",
        "close_strength",
        "base_range_30d",
    ]:
        assert col in result.columns


# --- Volume features ---


def test_volume_ma():
    df = make_ohlcv(50)
    vma = compute_volume_ma(df["volume"], 20)
    assert vma.notna().sum() == 31


def test_volume_ratio_near_one():
    df = make_ohlcv(50)
    vma = compute_volume_ma(df["volume"], 20)
    ratio = compute_volume_ratio(df["volume"], vma)
    # Average should be near 1
    assert 0.5 < ratio.dropna().mean() < 2.0


# --- Volatility features ---


def test_atr14_positive():
    df = make_ohlcv(50)
    atr = compute_atr(df["high"], df["low"], df["close"])
    assert (atr.dropna() > 0).all()


def test_volatility_20d_positive():
    df = make_ohlcv(100)
    vol = compute_volatility(df["close"], 20)
    assert (vol.dropna() > 0).all()


# --- Relative strength ---


def test_relative_strength_zero_when_equal():
    df = make_ohlcv(100, seed=1)
    rs = compute_relative_strength(df["close"], df["close"], 20)
    # RS against self should be 0
    assert (rs.dropna().abs() < 1e-10).all()


def test_relative_strength_features():
    df = make_ohlcv(200, seed=1)
    bench = make_ohlcv(200, seed=2)
    result = compute_relative_strength_features(df, bench)
    assert "rs_20d_vs_vnindex" in result.columns
    assert "rs_60d_vs_vnindex" in result.columns


# --- Integration ---


def test_build_features_for_symbol_integration():
    from vnalpha.features.build_features import build_features_for_symbol

    df = make_ohlcv(200)
    bench = make_ohlcv(200, seed=99)
    result = build_features_for_symbol(df, bench)
    assert not result.empty
    for col in ["ma20", "ma50", "atr14", "volume_ratio", "rs_20d_vs_vnindex"]:
        assert col in result.columns


def test_build_features_insufficient_history():
    from vnalpha.features.build_features import build_features_for_symbol

    df = make_ohlcv(15)  # < 20 bars
    result = build_features_for_symbol(df)
    assert result.empty


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
            "1D",
            str(d.date()),
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
        "INSERT INTO canonical_ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    return df


def test_build_features_exact_date_metadata():
    """When bar date == target date, as_of_bar_date == target_date, status CURRENT."""
    from vnalpha.features.build_features import build_features

    conn = _make_conn_with_schema()
    target = "2024-06-28"
    _insert_ohlcv(conn, "FPT", end_date=target)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    result = build_features(conn, target, universe=["FPT"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT as_of_bar_date, feature_data_status, source_row_count, feature_build_version, feature_generated_at "
        "FROM feature_snapshot WHERE symbol = 'FPT' AND date = ?",
        [target],
    ).fetchone()
    assert row is not None
    as_of_bar_date, status, src_count, build_ver, gen_at = row
    assert str(as_of_bar_date) == target
    assert status == "EXACT_DATE"
    assert src_count == 200
    assert build_ver is not None
    assert gen_at is not None


def test_build_features_stale_date_metadata():
    """When last bar is before target_date, status should be STALE."""
    from vnalpha.features.build_features import build_features

    conn = _make_conn_with_schema()
    # Insert data ending 3 days before target
    data_end = "2024-06-25"
    target = "2024-06-28"
    _insert_ohlcv(conn, "ACB", end_date=data_end)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    result = build_features(conn, target, universe=["ACB"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT as_of_bar_date, feature_data_status FROM feature_snapshot "
        "WHERE symbol = 'ACB' AND date = ?",
        [target],
    ).fetchone()
    assert row is not None
    as_of_bar_date, status = row
    assert str(as_of_bar_date) < target
    assert status == "STALE_DATE"


def test_build_features_missing_benchmark():
    """When benchmark is missing, benchmark_as_of_bar_date is None, RS features are NaN."""
    from vnalpha.features.build_features import build_features

    conn = _make_conn_with_schema()
    target = "2024-06-28"
    _insert_ohlcv(conn, "VNM", end_date=target)
    # No VNINDEX inserted

    result = build_features(conn, target, universe=["VNM"])
    assert result["built"] == 1

    row = conn.execute(
        "SELECT benchmark_as_of_bar_date, benchmark_row_count, rs_20d_vs_vnindex "
        "FROM feature_snapshot WHERE symbol = 'VNM' AND date = ?",
        [target],
    ).fetchone()
    assert row is not None
    bench_as_of, bench_count, rs = row
    assert bench_as_of is None
    assert bench_count == 0
    # RS should be NULL (NaN stored as None in DuckDB)
    assert rs is None


def test_build_features_insufficient_history_skipped():
    """Symbols with < 20 bars are skipped and do not appear in feature_snapshot."""
    from vnalpha.features.build_features import build_features

    conn = _make_conn_with_schema()
    target = "2024-06-28"
    # Insert only 15 bars
    _insert_ohlcv(conn, "TINY", n=15, end_date=target)
    _insert_ohlcv(conn, "VNINDEX", end_date=target, seed=99)

    result = build_features(conn, target, universe=["TINY"])
    assert result["skipped"] == 1
    assert result["built"] == 0

    count = conn.execute(
        "SELECT COUNT(*) FROM feature_snapshot WHERE symbol = 'TINY'"
    ).fetchone()[0]
    assert count == 0
