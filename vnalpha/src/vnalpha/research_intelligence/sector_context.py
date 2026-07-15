"""Typed active-universe inputs for sector strength research snapshots."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from statistics import median
from types import MappingProxyType

import duckdb


@dataclass(frozen=True, slots=True)
class SectorInputContext:
    """Classified active membership and exact usable feature inputs."""

    active_symbols: tuple[str, ...]
    sector_by_symbol: Mapping[str, str]
    member_counts: Mapping[str, int]
    eligible_rows: tuple[FeatureRow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_symbols", tuple(self.active_symbols))
        object.__setattr__(
            self, "sector_by_symbol", MappingProxyType(dict(self.sector_by_symbol))
        )
        object.__setattr__(
            self, "member_counts", MappingProxyType(dict(self.member_counts))
        )
        object.__setattr__(self, "eligible_rows", tuple(self.eligible_rows))

    @property
    def excluded_symbols(self) -> tuple[str, ...]:
        """Active symbols without an exact usable feature row."""
        eligible_symbols = {row.symbol for row in self.eligible_rows}
        return tuple(
            symbol for symbol in self.active_symbols if symbol not in eligible_symbols
        )

    @property
    def unclassified_eligible_count(self) -> int:
        """Eligible rows whose active symbol has no nonblank sector metadata."""
        return sum(
            row.symbol not in self.sector_by_symbol for row in self.eligible_rows
        )

    @property
    def classified_eligible_count(self) -> int:
        """Eligible rows that can be assigned to a source sector."""
        return len(self.eligible_rows) - self.unclassified_eligible_count

    @property
    def metadata_coverage(self) -> float:
        """The classified share of exact usable feature rows."""
        return (
            self.classified_eligible_count / len(self.eligible_rows)
            if self.eligible_rows
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class FeatureRow:
    symbol: str
    close: float
    ma20: float
    ma50: float
    return20: float
    return60: float
    rs20: float
    rs60: float


@dataclass(frozen=True, slots=True)
class SectorAggregate:
    sector: str
    member_count: int
    rows: tuple[FeatureRow, ...]

    @property
    def eligible_count(self) -> int:
        return len(self.rows)

    @property
    def score(self) -> float:
        return (
            0.40 * self.median_rs20
            + 0.30 * self.median_return20
            + 0.20 * (self.pct_above_ma20 - 0.50)
            + 0.10 * (self.leadership_count / self.eligible_count)
        )

    @property
    def median_return20(self) -> float:
        return median(row.return20 for row in self.rows)

    @property
    def median_return60(self) -> float:
        return median(row.return60 for row in self.rows)

    @property
    def median_rs20(self) -> float:
        return median(row.rs20 for row in self.rows)

    @property
    def median_rs60(self) -> float:
        return median(row.rs60 for row in self.rows)

    @property
    def pct_above_ma20(self) -> float:
        return sum(row.close > row.ma20 for row in self.rows) / self.eligible_count

    @property
    def pct_above_ma50(self) -> float:
        return sum(row.close > row.ma50 for row in self.rows) / self.eligible_count

    @property
    def leadership_count(self) -> int:
        return sum(row.rs20 > 0 for row in self.rows)

    @property
    def rotation(self) -> str:
        if self.median_rs20 > 0 and self.median_rs20 > self.median_rs60:
            return "IMPROVING"
        if self.median_rs20 < 0 and self.median_rs20 < self.median_rs60:
            return "WEAKENING"
        return "STABLE"


def load_sector_input_context(
    conn: duckdb.DuckDBPyConnection, as_of_date: date
) -> SectorInputContext:
    """Load active membership and exact usable feature rows for one date."""
    membership_rows: list[tuple[str, str | None]] = conn.execute(
        """
        SELECT symbol, sector
        FROM symbol_master
        WHERE is_active = TRUE
        ORDER BY symbol
        """
    ).fetchall()
    active_symbols = tuple(row[0] for row in membership_rows)
    sector_by_symbol = {
        symbol: sector.strip()
        for symbol, sector in membership_rows
        if sector is not None and sector.strip()
    }
    member_counts: defaultdict[str, int] = defaultdict(int)
    for sector in sector_by_symbol.values():
        member_counts[sector] += 1
    eligible_values: list[
        tuple[str, float, float, float, float, float, float, float]
    ] = conn.execute(
        """
        SELECT f.symbol, f.close, f.ma20, f.ma50, f.return_20d, f.return_60d,
               f.rs_20d_vs_vnindex, f.rs_60d_vs_vnindex
        FROM feature_snapshot AS f
        JOIN symbol_master AS s ON s.symbol = f.symbol
        WHERE s.is_active = TRUE AND f.date = ? AND f.as_of_bar_date = ?
          AND f.feature_data_status = 'EXACT_DATE'
          AND f.feature_profile IN ('STANDARD_120', 'FULL_252')
          AND f.neutral_completeness = 'COMPLETE'
          AND f.relative_strength_completeness = 'COMPLETE'
          AND f.close IS NOT NULL AND f.ma20 IS NOT NULL AND f.ma50 IS NOT NULL
          AND f.return_20d IS NOT NULL AND f.return_60d IS NOT NULL
          AND f.rs_20d_vs_vnindex IS NOT NULL AND f.rs_60d_vs_vnindex IS NOT NULL
        ORDER BY f.symbol
        """,
        [as_of_date, as_of_date],
    ).fetchall()
    eligible_rows = tuple(
        FeatureRow(
            symbol=symbol,
            close=close,
            ma20=ma20,
            ma50=ma50,
            return20=return20,
            return60=return60,
            rs20=rs20,
            rs60=rs60,
        )
        for symbol, close, ma20, ma50, return20, return60, rs20, rs60 in eligible_values
    )
    return SectorInputContext(
        active_symbols=active_symbols,
        sector_by_symbol=sector_by_symbol,
        member_counts=member_counts,
        eligible_rows=eligible_rows,
    )


def aggregate_sector_context(
    context: SectorInputContext,
) -> tuple[SectorAggregate, ...]:
    """Group exact eligible rows under source-sector active membership."""
    grouped: defaultdict[str, list[FeatureRow]] = defaultdict(list)
    for row in context.eligible_rows:
        sector = context.sector_by_symbol.get(row.symbol)
        if sector is not None:
            grouped[sector].append(row)
    return tuple(
        SectorAggregate(
            sector=sector,
            member_count=member_count,
            rows=tuple(grouped[sector]),
        )
        for sector, member_count in sorted(context.member_counts.items())
    )
