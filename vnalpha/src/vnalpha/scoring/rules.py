"""Rule-based signal rules for alpha scoring."""
from __future__ import annotations
from typing import Any


def rule_price_above_ma20(features: dict[str, Any]) -> bool:
    """Price above MA20."""
    close = features.get("close")
    ma20 = features.get("ma20")
    if close is None or ma20 is None:
        return False
    return close > ma20


def rule_price_above_ma50(features: dict[str, Any]) -> bool:
    """Price above MA50."""
    close = features.get("close")
    ma50 = features.get("ma50")
    if close is None or ma50 is None:
        return False
    return close > ma50


def rule_ma20_above_ma50(features: dict[str, Any]) -> bool:
    """MA20 above MA50 (uptrend)."""
    ma20 = features.get("ma20")
    ma50 = features.get("ma50")
    if ma20 is None or ma50 is None:
        return False
    return ma20 > ma50


def rule_ma50_above_ma100(features: dict[str, Any]) -> bool:
    """MA50 above MA100 (longer uptrend)."""
    ma50 = features.get("ma50")
    ma100 = features.get("ma100")
    if ma50 is None or ma100 is None:
        return False
    return ma50 > ma100


def rule_positive_ma20_slope(features: dict[str, Any]) -> bool:
    """MA20 slope is positive."""
    slope = features.get("ma20_slope")
    return slope is not None and slope > 0


def rule_volume_expansion(features: dict[str, Any], threshold: float = 1.2) -> bool:
    """Current volume ratio > threshold (expansion)."""
    ratio = features.get("volume_ratio")
    return ratio is not None and ratio > threshold


def rule_close_near_high(features: dict[str, Any], threshold: float = 0.7) -> bool:
    """Close strength > threshold (closing near session high)."""
    cs = features.get("close_strength")
    return cs is not None and cs > threshold


def rule_rs_positive_20d(features: dict[str, Any]) -> bool:
    """20-day relative strength vs VNINDEX is positive."""
    rs = features.get("rs_20d_vs_vnindex")
    return rs is not None and rs > 0


def rule_base_compression(features: dict[str, Any], max_range: float = 0.08) -> bool:
    """Base range (compression) < threshold (tight base)."""
    br = features.get("base_range_30d")
    return br is not None and br < max_range


def rule_near_52w_high(features: dict[str, Any], threshold: float = -0.05) -> bool:
    """Distance to 52-week high > threshold (within 5% of 52w high)."""
    dist = features.get("distance_to_52w_high")
    return dist is not None and dist > threshold


def rule_not_extended_from_ma20(features: dict[str, Any], max_distance: float = 0.15) -> bool:
    """Not extended > max_distance from MA20."""
    dist = features.get("distance_to_ma20")
    return dist is not None and abs(dist) < max_distance
