"""Versioned production policies for deterministic market context."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, sqrt
from typing import Final


@dataclass(frozen=True, slots=True)
class MarketRegimePolicy:
    """Thresholds and eligibility rules for one market-regime methodology."""

    methodology_version: str
    minimum_eligible_symbols: int
    minimum_breadth_coverage: float
    minimum_exchange_coverage: float
    minimum_liquidity_coverage: float
    minimum_average_traded_value: float
    maximum_staleness_days: int
    allowed_feature_profiles: tuple[str, ...]
    allowed_security_types: tuple[str, ...]
    allow_missing_security_type: bool
    minimum_ma50_slope: float
    high_volatility_threshold: float
    risk_on_pct_above_ma20: float
    risk_on_pct_above_ma50: float
    risk_on_pct_positive_return20: float
    risk_off_pct_above_ma20: float

    def __post_init__(self) -> None:
        if self.minimum_eligible_symbols < 1:
            raise ValueError("minimum_eligible_symbols must be positive")
        if self.minimum_average_traded_value < 0:
            raise ValueError("minimum_average_traded_value must not be negative")
        if self.maximum_staleness_days < 0:
            raise ValueError("maximum_staleness_days must not be negative")
        for name, value in (
            ("minimum_breadth_coverage", self.minimum_breadth_coverage),
            ("minimum_exchange_coverage", self.minimum_exchange_coverage),
            ("minimum_liquidity_coverage", self.minimum_liquidity_coverage),
            ("risk_on_pct_above_ma20", self.risk_on_pct_above_ma20),
            ("risk_on_pct_above_ma50", self.risk_on_pct_above_ma50),
            (
                "risk_on_pct_positive_return20",
                self.risk_on_pct_positive_return20,
            ),
            ("risk_off_pct_above_ma20", self.risk_off_pct_above_ma20),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if not self.allowed_feature_profiles:
            raise ValueError("allowed_feature_profiles must not be empty")
        if not self.allowed_security_types:
            raise ValueError("allowed_security_types must not be empty")


@dataclass(frozen=True, slots=True)
class SectorScoreWeights:
    """Normalized deterministic score weights for sector ranking."""

    relative_strength20: float
    return20: float
    pct_above_ma20: float
    pct_above_ma50: float
    leadership_share: float

    def __post_init__(self) -> None:
        values = (
            self.relative_strength20,
            self.return20,
            self.pct_above_ma20,
            self.pct_above_ma50,
            self.leadership_share,
        )
        if any(value < 0 for value in values):
            raise ValueError("sector score weights must not be negative")
        if not isclose(sum(values), 1.0, abs_tol=1e-9):
            raise ValueError("sector score weights must sum to one")


@dataclass(frozen=True, slots=True)
class SectorStrengthPolicy:
    """Thresholds and robust aggregation rules for sector ranking."""

    methodology_version: str
    minimum_sector_members: int
    minimum_eligible_members: int
    minimum_sector_coverage: float
    minimum_metadata_coverage: float
    minimum_taxonomy_coverage: float
    minimum_liquidity_coverage: float
    minimum_average_traded_value: float
    maximum_staleness_days: int
    allowed_feature_profiles: tuple[str, ...]
    allowed_security_types: tuple[str, ...]
    allow_missing_security_type: bool
    winsor_lower_quantile: float
    winsor_upper_quantile: float
    concentration_warning_threshold: float
    score_weights: SectorScoreWeights

    def __post_init__(self) -> None:
        if self.minimum_sector_members < 1:
            raise ValueError("minimum_sector_members must be positive")
        if self.minimum_eligible_members < 1:
            raise ValueError("minimum_eligible_members must be positive")
        if self.minimum_eligible_members > self.minimum_sector_members:
            raise ValueError(
                "minimum_eligible_members must not exceed minimum_sector_members"
            )
        if self.minimum_average_traded_value < 0:
            raise ValueError("minimum_average_traded_value must not be negative")
        if self.maximum_staleness_days < 0:
            raise ValueError("maximum_staleness_days must not be negative")
        for name, value in (
            ("minimum_sector_coverage", self.minimum_sector_coverage),
            ("minimum_metadata_coverage", self.minimum_metadata_coverage),
            ("minimum_taxonomy_coverage", self.minimum_taxonomy_coverage),
            ("minimum_liquidity_coverage", self.minimum_liquidity_coverage),
            ("winsor_lower_quantile", self.winsor_lower_quantile),
            ("winsor_upper_quantile", self.winsor_upper_quantile),
            ("concentration_warning_threshold", self.concentration_warning_threshold),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.winsor_lower_quantile > self.winsor_upper_quantile:
            raise ValueError("winsor quantiles are reversed")
        if not self.allowed_feature_profiles:
            raise ValueError("allowed_feature_profiles must not be empty")
        if not self.allowed_security_types:
            raise ValueError("allowed_security_types must not be empty")


_LEGACY_SCORE_WEIGHTS: Final = SectorScoreWeights(
    relative_strength20=0.40,
    return20=0.30,
    pct_above_ma20=0.20,
    pct_above_ma50=0.00,
    leadership_share=0.10,
)

_PRODUCTION_SCORE_WEIGHTS: Final = SectorScoreWeights(
    relative_strength20=0.35,
    return20=0.25,
    pct_above_ma20=0.15,
    pct_above_ma50=0.10,
    leadership_share=0.15,
)

LEGACY_MARKET_REGIME_POLICY: Final = MarketRegimePolicy(
    methodology_version="market-regime-v1",
    minimum_eligible_symbols=5,
    minimum_breadth_coverage=0.0,
    minimum_exchange_coverage=0.0,
    minimum_liquidity_coverage=0.0,
    minimum_average_traded_value=0.0,
    maximum_staleness_days=0,
    allowed_feature_profiles=("MINIMAL_20", "STANDARD_120", "FULL_252"),
    allowed_security_types=("COMMON_EQUITY",),
    allow_missing_security_type=True,
    minimum_ma50_slope=0.0,
    high_volatility_threshold=0.30 / sqrt(252),
    risk_on_pct_above_ma20=0.60,
    risk_on_pct_above_ma50=0.50,
    risk_on_pct_positive_return20=0.0,
    risk_off_pct_above_ma20=0.40,
)

PRODUCTION_MARKET_REGIME_POLICY: Final = MarketRegimePolicy(
    methodology_version="market-regime-v2",
    minimum_eligible_symbols=20,
    minimum_breadth_coverage=0.70,
    minimum_exchange_coverage=0.67,
    minimum_liquidity_coverage=0.70,
    minimum_average_traded_value=1_000_000.0,
    maximum_staleness_days=0,
    allowed_feature_profiles=("STANDARD_120", "FULL_252"),
    allowed_security_types=("COMMON_EQUITY",),
    allow_missing_security_type=False,
    minimum_ma50_slope=0.0,
    high_volatility_threshold=0.30 / sqrt(252),
    risk_on_pct_above_ma20=0.60,
    risk_on_pct_above_ma50=0.50,
    risk_on_pct_positive_return20=0.55,
    risk_off_pct_above_ma20=0.40,
)

LEGACY_SECTOR_STRENGTH_POLICY: Final = SectorStrengthPolicy(
    methodology_version="sector-strength-v1",
    minimum_sector_members=3,
    minimum_eligible_members=3,
    minimum_sector_coverage=0.0,
    minimum_metadata_coverage=0.0,
    minimum_taxonomy_coverage=0.0,
    minimum_liquidity_coverage=0.0,
    minimum_average_traded_value=0.0,
    maximum_staleness_days=0,
    allowed_feature_profiles=("STANDARD_120", "FULL_252"),
    allowed_security_types=("COMMON_EQUITY",),
    allow_missing_security_type=True,
    winsor_lower_quantile=0.0,
    winsor_upper_quantile=1.0,
    concentration_warning_threshold=1.0,
    score_weights=_LEGACY_SCORE_WEIGHTS,
)

PRODUCTION_SECTOR_STRENGTH_POLICY: Final = SectorStrengthPolicy(
    methodology_version="sector-strength-v2",
    minimum_sector_members=5,
    minimum_eligible_members=4,
    minimum_sector_coverage=0.60,
    minimum_metadata_coverage=0.80,
    minimum_taxonomy_coverage=0.70,
    minimum_liquidity_coverage=0.70,
    minimum_average_traded_value=1_000_000.0,
    maximum_staleness_days=0,
    allowed_feature_profiles=("STANDARD_120", "FULL_252"),
    allowed_security_types=("COMMON_EQUITY",),
    allow_missing_security_type=False,
    winsor_lower_quantile=0.10,
    winsor_upper_quantile=0.90,
    concentration_warning_threshold=0.45,
    score_weights=_PRODUCTION_SCORE_WEIGHTS,
)
