"""Core scoring logic: compute composite score for a symbol."""

from __future__ import annotations

import math
from typing import Any, Optional

from vnalpha.core.types import CandidateClass, SetupType
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY, ScoringPolicy
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


def compute_trend_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 based on price/MA alignment."""
    rules = {
        "price_above_ma20": rule_price_above_ma20(features),
        "price_above_ma50": rule_price_above_ma50(features),
        "ma20_above_ma50": rule_ma20_above_ma50(features),
        "ma50_above_ma100": rule_ma50_above_ma100(features),
        "positive_ma20_slope": rule_positive_ma20_slope(features),
    }
    return sum(
        policy.number("trend_rule_weights", name) * value
        for name, value in rules.items()
    )


def compute_relative_strength_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 based on relative performance vs benchmark."""
    rs20 = _safe(features.get("rs_20d_vs_vnindex"))
    rs60 = _safe(features.get("rs_60d_vs_vnindex"))
    # Normalize: RS of +5% → score of 0.75
    floor = policy.number("normalization", "relative_strength_floor")
    width = policy.number("normalization", "relative_strength_range")
    score20 = min(1.0, max(0.0, (rs20 - floor) / width))
    score60 = min(1.0, max(0.0, (rs60 - floor) / width))
    return (
        policy.number("relative_strength_weights", "rs20") * score20
        + policy.number("relative_strength_weights", "rs60") * score60
    )


def compute_volume_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 based on volume expansion."""
    ratio = _safe(features.get("volume_ratio"), 1.0)
    # volume_ratio of 2.0 → score 1.0; 1.0 → 0.5; 0.5 → 0.25
    return min(1.0, max(0.0, ratio / policy.number("normalization", "volume_divisor")))


def compute_base_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 based on base tightness."""
    base_range = _safe(features.get("base_range_30d"), 0.15)
    # 0% range → 1.0; 15% range → 0.0
    return min(
        1.0, max(0.0, 1.0 - base_range / policy.number("normalization", "base_range"))
    )


def compute_breakout_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 for breakout-style setups."""
    components = {
        "near_52w_high": rule_near_52w_high(
            features, policy.number("breakout_thresholds", "near_52w_high")
        ),
        "close_strength": rule_close_near_high(
            features, policy.number("breakout_thresholds", "close_strength")
        ),
        "volume_expansion": rule_volume_expansion(
            features, policy.number("breakout_thresholds", "volume_expansion")
        ),
        "base_compression": rule_base_compression(
            features, policy.number("breakout_thresholds", "base_compression")
        ),
    }
    return sum(
        policy.number("breakout_rule_weights", name) * value
        for name, value in components.items()
    )


def compute_risk_quality_score(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> float:
    """Score 0-1 penalising risk flags."""
    flags = compute_risk_flags(features)
    penalty = len(flags) * policy.number("risk", "flag_penalty")
    return max(0.0, 1.0 - penalty)


def compute_composite_score(
    features: dict[str, Any], *, policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> dict[str, Any]:
    """Compute composite score and sub-scores for a symbol.

    Returns:
        dict with "score", "candidate_class", "setup_type",
        "trend_score", "relative_strength_score", "volume_score",
        "base_score", "breakout_score", "risk_quality_score",
        "risk_flags" list.
    """
    trend = compute_trend_score(features, policy)
    rs = compute_relative_strength_score(features, policy)
    vol = compute_volume_score(features, policy)
    base = compute_base_score(features, policy)
    breakout = compute_breakout_score(features, policy)
    risk_quality = compute_risk_quality_score(features, policy)

    score = (
        policy.number("weights", "trend") * trend
        + policy.number("weights", "relative_strength") * rs
        + policy.number("weights", "volume") * vol
        + policy.number("weights", "base") * base
        + policy.number("weights", "breakout") * breakout
        + policy.number("weights", "risk_quality") * risk_quality
    )

    # Classify candidate
    candidate_class = _classify_candidate(score, features, policy)
    setup_type = _detect_setup(features, policy)
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
        "scoring_policy_id": policy.policy_id,
        "scoring_policy_version": policy.version,
        "scoring_policy_hash": policy.payload_hash,
        "scoring_policy_status": policy.lifecycle_status.value,
    }


def _classify_candidate(
    score: float,
    features: dict[str, Any],
    policy: ScoringPolicy = BASELINE_SCORING_POLICY,
) -> str:
    """Map composite score + features to canonical CandidateClass.

    Canonical ontology:
        STRONG_CANDIDATE  — score >= 0.70, strong setup or momentum
        WATCH_CANDIDATE   — score >= 0.50, moderate setup
        WEAK_CANDIDATE    — score >= 0.30, marginal
        IGNORE            — score < 0.30, insufficient evidence
    """
    if score >= policy.number("candidate_thresholds", "strong"):
        return CandidateClass.STRONG_CANDIDATE.value
    elif score >= policy.number("candidate_thresholds", "watch"):
        return CandidateClass.WATCH_CANDIDATE.value
    elif score >= policy.number("candidate_thresholds", "weak"):
        return CandidateClass.WEAK_CANDIDATE.value
    else:
        return CandidateClass.IGNORE.value


def _detect_setup(
    features: dict[str, Any], policy: ScoringPolicy = BASELINE_SCORING_POLICY
) -> str:
    """Detect primary setup type from features using canonical SetupType values.

    Canonical ontology:
        ACCUMULATION_BASE       — tight base near 52w high
        BREAKOUT_ATTEMPT        — near 52w high + volume expansion
        MOMENTUM_CONTINUATION   — uptrend + price > MA
        PULLBACK_TO_TREND       — uptrend + close near MA20
        MEAN_REVERSION          — price below MA, volume expansion
        UNCLASSIFIED            — no clear pattern
    """
    if rule_base_compression(
        features, policy.number("setup_thresholds", "base_compression")
    ) and rule_near_52w_high(
        features, policy.number("setup_thresholds", "near_52w_high")
    ):
        if rule_volume_expansion(
            features, threshold=policy.number("setup_thresholds", "breakout_volume")
        ):
            return SetupType.BREAKOUT_ATTEMPT.value
        return SetupType.ACCUMULATION_BASE.value
    if rule_positive_ma20_slope(features) and rule_price_above_ma20(features):
        dist = _safe(features.get("distance_to_ma20"))
        if abs(dist) < policy.number("setup_thresholds", "pullback_distance"):
            return SetupType.PULLBACK_TO_TREND.value
        return SetupType.MOMENTUM_CONTINUATION.value
    if not rule_price_above_ma20(features) and rule_volume_expansion(
        features,
        threshold=policy.number("setup_thresholds", "breakout_volume"),
    ):
        return SetupType.MEAN_REVERSION.value
    return SetupType.UNCLASSIFIED.value
