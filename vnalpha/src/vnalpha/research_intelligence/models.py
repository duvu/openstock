from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class MarketRegimeSnapshot:
    as_of_date: date
    benchmark_symbol: str
    benchmark_bar_date: date
    close: float
    ma20: float
    ma50: float
    ma50_slope: float
    return20: float | None
    return60: float | None
    volatility20: float
    breadth_active_count: int
    breadth_eligible_count: int
    breadth_excluded_count: int
    breadth_coverage: float | None
    pct_above_ma20: float | None
    pct_above_ma50: float | None
    pct_positive_return20: float | None
    regime: str
    trend: str
    volatility: str
    quality: str
    caveats: tuple[str, ...]
    lineage: Mapping[str, str]
    methodology_version: str
    generated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "caveats", tuple(self.caveats))
        object.__setattr__(self, "lineage", MappingProxyType(dict(self.lineage)))


@dataclass(frozen=True, slots=True)
class SectorStrengthSnapshot:
    as_of_date: date
    sector: str
    rank: int
    member_count: int
    eligible_count: int
    median_return20: float
    median_return60: float
    median_rs20_vs_vnindex: float
    median_rs60_vs_vnindex: float
    pct_above_ma20: float
    pct_above_ma50: float
    leadership_count: int
    score: float
    rotation: str
    metadata_coverage: float
    unclassified_count: int
    quality: str
    caveats: tuple[str, ...]
    lineage: Mapping[str, str]
    methodology_version: str
    generated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "caveats", tuple(self.caveats))
        object.__setattr__(self, "lineage", MappingProxyType(dict(self.lineage)))


@dataclass(frozen=True, slots=True)
class SymbolSectorAlignment:
    symbol: str
    sector: str | None
    snapshot: SectorStrengthSnapshot | None
