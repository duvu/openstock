"""Core scoring logic: compute composite score for a symbol."""

from __future__ import annotations

import math
from typing import Any, Optional

from vnalpha.core.types import CandidateClass, SetupType
from vnalpha.scoring.risk_flags import compute_risk_flags
from vnalpha.scoring.rules import (
    rule_base_compression,
    rule_close_near_high,
    rule_ma20_above_ma50,
    rule_ma50_above_ma100,
    rule_near_52w_high,
    rule_positive_ma20_slope,
    rule_price_above_ma20,
    rule_price_above_ma50,
    rule_volume_expansion,
)


def _safe(v: Optional[float], default: float = 0.0) -> float:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    return float(v)


def compute_trend_score(features: dict[str, Any]) -> float:
    """Score 0-1 based on price/MA alignment."""
    rules = [
        rule_price_above_ma20(features),
        rule_price_above_ma50(features),
        rule_ma20_above_ma50(features),
        rule_ma50_above_ma100(features),
        rule_positive_ma20_slope(features),
    ]
    return sum(rules) / len(rules)


def compute_relative_strength_score(features: dict[str, Any]) -> float:
    """Score 0-1 based on relative performance vs benchmark."""
    rs20 = _safe(features.get("rs_20d_vs_vnindex"))
    rs60 = _safe(features.get("rs_60d_vs_vnindex"))
    # Normalize: RS of +5% → score of 0.75
    score20 = min(1.0, max(0.0, (rs20 + 0.05) / 0.1))
    score60 = min(1.0, max(0.0, (rs60 + 0.05) / 0.1))
    return 0.5 * score20 + 0.5 * score60


def compute_volume_score(features: dict[str, Any]) -> float:
    """Score 0-1 based on volume expansion."""
    ratio = _safe(features.get("volume_ratio"), 1.0)
    # volume_ratio of 2.0 → score 1.0; 1.0 → 0.5; 0.5 → 0.25
    return min(1.0, max(0.0, ratio / 2.0))


def compute_base_score(features: dict[str, Any]) -> float:
    """Score 0-1 based on base tightness."""
    base_range = _safe(features.get("base_range_30d"), 0.15)
    # 0% range → 1.0; 15% range → 0.0
    return min(1.0, max(0.0, 1.0 - base_range / 0.15))


def compute_breakout_score(features: dict[str, Any]) -> float:
    """Score 0-1 for breakout-style setups."""
    components = [
        rule_near_52w_high(features),
        rule_close_near_high(features),
        rule_volume_expansion(features),
        rule_base_compression(features),
    ]
    return sum(components) / len(components)


def compute_risk_quality_score(features: dict[str, Any]) -> float:
    """Score 0-1 penalising risk flags."""
    flags = compute_risk_flags(features)
    penalty = len(flags) * 0.2
    return max(0.0, 1.0 - penalty)


SCORE_WEIGHTS = {
    "trend": 0.30,
    "relative_strength": 0.25,
    "volume": 0.15,
    "base": 0.10,
    "breakout": 0.10,
    "risk_quality": 0.10,
}


def compute_composite_score(features: dict[str, Any]) -> dict[str, Any]:
    """Compute composite score and sub-scores for a symbol.

    Returns:
        dict with "score", "candidate_class", "setup_type",
        "trend_score", "relative_strength_score", "volume_score",
        "base_score", "breakout_score", "risk_quality_score",
        "risk_flags" list.
    """
    trend = compute_trend_score(features)
    rs = compute_relative_strength_score(features)
    vol = compute_volume_score(features)
    base = compute_base_score(features)
    breakout = compute_breakout_score(features)
    risk_quality = compute_risk_quality_score(features)

    score = (
        SCORE_WEIGHTS["trend"] * trend
        + SCORE_WEIGHTS["relative_strength"] * rs
        + SCORE_WEIGHTS["volume"] * vol
        + SCORE_WEIGHTS["base"] * base
        + SCORE_WEIGHTS["breakout"] * breakout
        + SCORE_WEIGHTS["risk_quality"] * risk_quality
    )

    # Classify candidate
    candidate_class = _classify_candidate(score, features)
    setup_type = _detect_setup(features)
    risk_flags = compute_risk_flags(features)

    return {
        "score": round(score, 4),
        "candidate_class": candidate_class,
        "setup_type": setup_type,
        "trend_score": round(trend, 4),
        "relative_strength_score": round(rs, 4),
        "volume_score": round(vol, 4),
        "base_score": round(base, 4),
        "breakout_score": round(breakout, 4),
        "risk_quality_score": round(risk_quality, 4),
        "risk_flags": [f.value for f in risk_flags],
    }


def _classify_candidate(score: float, features: dict[str, Any]) -> str:
    """Map composite score + features to canonical CandidateClass.

    Canonical ontology:
        STRONG_CANDIDATE  — score >= 0.70, strong setup or momentum
        WATCH_CANDIDATE   — score >= 0.50, moderate setup
        WEAK_CANDIDATE    — score >= 0.30, marginal
        IGNORE            — score < 0.30, insufficient evidence
    """
    if score >= 0.70:
        return CandidateClass.STRONG_CANDIDATE.value
    elif score >= 0.50:
        return CandidateClass.WATCH_CANDIDATE.value
    elif score >= 0.30:
        return CandidateClass.WEAK_CANDIDATE.value
    else:
        return CandidateClass.IGNORE.value


def _detect_setup(features: dict[str, Any]) -> str:
    """Detect primary setup type from features using canonical SetupType values.

    Canonical ontology:
        ACCUMULATION_BASE       — tight base near 52w high
        BREAKOUT_ATTEMPT        — near 52w high + volume expansion
        MOMENTUM_CONTINUATION   — uptrend + price > MA
        PULLBACK_TO_TREND       — uptrend + close near MA20
        MEAN_REVERSION          — price below MA, volume expansion
        UNCLASSIFIED            — no clear pattern
    """
    if rule_base_compression(features) and rule_near_52w_high(features):
        if rule_volume_expansion(features, threshold=1.5):
            return SetupType.BREAKOUT_ATTEMPT.value
        return SetupType.ACCUMULATION_BASE.value
    if rule_positive_ma20_slope(features) and rule_price_above_ma20(features):
        dist = _safe(features.get("distance_to_ma20"))
        if abs(dist) < 0.03:
            return SetupType.PULLBACK_TO_TREND.value
        return SetupType.MOMENTUM_CONTINUATION.value
    if not rule_price_above_ma20(features) and rule_volume_expansion(
        features, threshold=1.5
    ):
        return SetupType.MEAN_REVERSION.value
    return SetupType.UNCLASSIFIED.value
