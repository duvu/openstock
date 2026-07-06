"""Tests for the alpha scoring engine."""

from vnalpha.core.types import RiskFlag
from vnalpha.scoring.risk_flags import compute_risk_flags
from vnalpha.scoring.rules import (
    rule_base_compression,
    rule_price_above_ma20,
    rule_volume_expansion,
)
from vnalpha.scoring.score import (
    compute_composite_score,
    compute_trend_score,
    compute_volume_score,
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


def test_rule_price_above_ma20_false():
    assert rule_price_above_ma20(WEAK_FEATURES) is False


def test_rule_volume_expansion_true():
    assert rule_volume_expansion(STRONG_FEATURES) is True


def test_rule_volume_expansion_false():
    assert rule_volume_expansion(WEAK_FEATURES) is False


def test_rule_base_compression_detects_tight():
    assert rule_base_compression(STRONG_FEATURES) is True


def test_rule_base_compression_rejects_wide():
    assert rule_base_compression(WEAK_FEATURES) is False


# --- Risk flags ---

def test_no_risk_flags_for_strong():
    flags = compute_risk_flags(STRONG_FEATURES)
    assert RiskFlag.THIN_VOLUME not in flags


def test_thin_volume_detected():
    flags = compute_risk_flags(WEAK_FEATURES)
    assert RiskFlag.THIN_VOLUME in flags


def test_high_atr_detected():
    flags = compute_risk_flags(WEAK_FEATURES)
    assert RiskFlag.HIGH_ATR in flags


def test_overbought_not_flagged_for_strong():
    flags = compute_risk_flags(STRONG_FEATURES)
    assert RiskFlag.OVERBOUGHT not in flags


# --- Scores ---

def test_trend_score_strong_is_high():
    score = compute_trend_score(STRONG_FEATURES)
    assert score >= 0.8, f"Expected trend score >= 0.8, got {score}"


def test_trend_score_weak_is_low():
    score = compute_trend_score(WEAK_FEATURES)
    assert score <= 0.3, f"Expected trend score <= 0.3, got {score}"


def test_volume_score_range():
    score_strong = compute_volume_score(STRONG_FEATURES)
    score_weak = compute_volume_score(WEAK_FEATURES)
    assert 0.0 <= score_strong <= 1.0
    assert 0.0 <= score_weak <= 1.0
    assert score_strong > score_weak


def test_composite_score_range():
    result = compute_composite_score(STRONG_FEATURES)
    assert 0.0 <= result["score"] <= 1.0
    assert "candidate_class" in result
    assert "setup_type" in result
    assert "risk_flags" in result


def test_composite_score_uses_canonical_candidate_class():
    """compute_composite_score returns canonical CandidateClass values."""
    from vnalpha.core.types import CandidateClass, SetupType
    canonical_classes = {c.value for c in CandidateClass}
    canonical_setups = {s.value for s in SetupType}

    for features in [STRONG_FEATURES, WEAK_FEATURES]:
        result = compute_composite_score(features)
        assert result["candidate_class"] in canonical_classes, (
            f"Non-canonical candidate_class: {result['candidate_class']!r}"
        )
        assert result["setup_type"] in canonical_setups, (
            f"Non-canonical setup_type: {result['setup_type']!r}"
        )


def test_strong_features_not_ignore():
    """Strong features should not classify as IGNORE."""
    result = compute_composite_score(STRONG_FEATURES)
    assert result["candidate_class"] != "IGNORE", (
        f"STRONG_FEATURES incorrectly classified as IGNORE (score={result['score']})"
    )


def test_composite_score_strong_beats_weak():
    strong_result = compute_composite_score(STRONG_FEATURES)
    weak_result = compute_composite_score(WEAK_FEATURES)
    assert strong_result["score"] > weak_result["score"], (
        f"Strong {strong_result['score']} should beat weak {weak_result['score']}"
    )


def test_composite_score_handles_none_features():
    empty_features = dict.fromkeys(STRONG_FEATURES)
    result = compute_composite_score(empty_features)
    assert 0.0 <= result["score"] <= 1.0


# --- Watchlist integration ---

def test_generate_watchlist():
    from vnalpha.scoring.generate_watchlist import save_watchlist, score_universe
    from vnalpha.warehouse.connection import in_memory_connection
    from vnalpha.warehouse.migrations import run_migrations

    conn = in_memory_connection()
    run_migrations(conn=conn)

    # Insert feature snapshot rows
    feature_cols = ["symbol", "date"] + list(STRONG_FEATURES.keys())
    strong_row = ["FPT", "2024-01-02"] + list(STRONG_FEATURES.values())
    weak_row = ["VNM", "2024-01-02"] + list(WEAK_FEATURES.values())

    for row in [strong_row, weak_row]:
        placeholders = ", ".join(["?"] * len(row))
        conn.execute(
            f"INSERT INTO feature_snapshot ({', '.join(feature_cols)}) VALUES ({placeholders})",
            row,
        )

    candidates = score_universe(conn, "2024-01-02")
    assert len(candidates) == 2
    assert candidates[0]["symbol"] == "FPT"  # highest score first

    saved = save_watchlist(conn, "2024-01-02", candidates, top_n=10, min_score=0.0)
    assert saved == 2

    from vnalpha.warehouse.repositories import get_watchlist
    wl = get_watchlist(conn, "2024-01-02")
    assert len(wl) == 2
    assert wl[0]["symbol"] == "FPT"
    conn.close()
