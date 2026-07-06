"""Risk flag detection for alpha candidates."""
from __future__ import annotations

from typing import Any, List

from vnalpha.core.types import RiskFlag


def detect_thin_volume(features: dict[str, Any], min_volume: float = 100_000) -> bool:
    """Volume MA20 below minimum threshold."""
    vma = features.get("volume_ma20")
    return vma is not None and vma < min_volume


def detect_high_atr(features: dict[str, Any], max_atr_pct: float = 0.05) -> bool:
    """ATR14 / close > max_atr_pct (high daily range = high risk)."""
    atr = features.get("atr14")
    close = features.get("close")
    if atr is None or close is None or close == 0:
        return False
    return (atr / close) > max_atr_pct


def detect_overbought(features: dict[str, Any], threshold: float = 0.20) -> bool:
    """Price extended > threshold above MA20 (overbought)."""
    dist = features.get("distance_to_ma20")
    return dist is not None and dist > threshold


def detect_extended_from_ma(features: dict[str, Any], threshold: float = 0.12) -> bool:
    """Price extended > threshold from MA20."""
    dist = features.get("distance_to_ma20")
    return dist is not None and abs(dist) > threshold


def detect_near_resistance(features: dict[str, Any], threshold: float = 0.02) -> bool:
    """Price within threshold of 52-week high (near resistance)."""
    dist = features.get("distance_to_52w_high")
    return dist is not None and dist > -threshold


def compute_risk_flags(features: dict[str, Any]) -> List[RiskFlag]:
    """Compute all risk flags for a set of features."""
    flags = []
    if detect_thin_volume(features):
        flags.append(RiskFlag.THIN_VOLUME)
    if detect_high_atr(features):
        flags.append(RiskFlag.HIGH_ATR)
    if detect_overbought(features):
        flags.append(RiskFlag.OVERBOUGHT)
    if detect_extended_from_ma(features):
        flags.append(RiskFlag.EXTENDED_FROM_MA)
    if detect_near_resistance(features):
        flags.append(RiskFlag.NEAR_RESISTANCE)
    return flags
