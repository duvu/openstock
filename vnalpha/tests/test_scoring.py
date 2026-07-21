"""Tests for the alpha scoring engine."""

from vnalpha.scoring.rules import (
    rule_price_above_ma20,
)

STRONG_FEATURES = {
    "close": 100.0,
    "ma20": 97.0,
    "ma50": 94.0,
    "ma100": 88.0,
    "ma20_slope": 0.002,
    "ma50_slope": 0.001,
    "volume_ma20": 1_000_000.0,
    "volume_ratio": 1.8,
    "atr14": 1.5,
    "return_20d": 0.08,
    "return_60d": 0.12,
    "rs_20d_vs_vnindex": 0.03,
    "rs_60d_vs_vnindex": 0.05,
    "distance_to_ma20": 0.031,
    "distance_to_52w_high": -0.02,
    "base_range_30d": 0.05,
    "close_strength": 0.75,
    "volatility_20d": 0.012,
}

WEAK_FEATURES = {
    "close": 80.0,
    "ma20": 90.0,  # below MA20
    "ma50": 92.0,  # below MA50
    "ma100": 88.0,
    "ma20_slope": -0.003,
    "ma50_slope": -0.001,
    "volume_ma20": 80_000.0,  # thin
    "volume_ratio": 0.6,
    "atr14": 6.0,  # high ATR
    "return_20d": -0.10,
    "return_60d": -0.08,
    "rs_20d_vs_vnindex": -0.05,
    "rs_60d_vs_vnindex": -0.08,
    "distance_to_ma20": -0.125,
    "distance_to_52w_high": -0.25,
    "base_range_30d": 0.20,
    "close_strength": 0.30,
    "volatility_20d": 0.030,
}


# --- Rules ---


def test_rule_price_above_ma20_true():
    assert rule_price_above_ma20(STRONG_FEATURES) is True


# --- Risk flags ---


# --- Scores ---


# --- Watchlist integration ---
