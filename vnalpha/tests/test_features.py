"""Tests for feature computations using synthetic data."""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from vnalpha.features.price import (
    compute_ma, compute_ma_slope, compute_distance_to_ma,
    compute_distance_to_52w_high, compute_return, compute_close_strength,
    compute_base_range, compute_price_features,
)
from vnalpha.features.volume import compute_volume_ma, compute_volume_ratio, compute_volume_features
from vnalpha.features.volatility import compute_atr, compute_volatility, compute_volatility_features
from vnalpha.features.relative_strength import compute_relative_strength, compute_relative_strength_features


def make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create synthetic OHLCV DataFrame with DatetimeIndex."""
    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "open": prices * (1 - rng.uniform(0, 0.005, n)),
        "high": prices * (1 + rng.uniform(0, 0.01, n)),
        "low": prices * (1 - rng.uniform(0, 0.01, n)),
        "close": prices,
        "volume": rng.integers(500_000, 2_000_000, n).astype(float),
    }, index=idx)


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
    for col in ["ma20", "ma50", "ma100", "ma20_slope", "ma50_slope",
                "distance_to_ma20", "return_20d", "return_60d", "close_strength", "base_range_30d"]:
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
