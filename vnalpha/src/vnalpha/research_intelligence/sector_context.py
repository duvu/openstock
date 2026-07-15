"""Policy-aware active-universe inputs for sector-strength snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median
from types import MappingProxyType

import duckdb

from vnalpha.research_intelligence.policy import (
    LEGACY_SECTOR_STRENGTH_POLICY,
    SectorStrengthPolicy,
)


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _security_type_allowed(
    security_type: str | None, policy: SectorStrengthPolicy
) -> bool:
    normalized = (security_type or "").strip().upper()
    if not normalized:
        return policy.allow_missing_security_type
    return normalized in policy.allowed_security_types


def _quantile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a quantile for an empty sequence")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return (
        ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction
    )


def _winsorized(
    values: Sequence[float], lower_quantile: float, upper_quantile: float
) -> tuple[tuple[float, ...], int]:
    lower = _quantile(values, lower_quantile)
    upper = _quantile(values, upper_quantile)
    capped = tuple(min(max(value, lower), upper) for value in values)
    return capped, sum(
        original != adjusted for original, adjusted in zip(values, capped, strict=True)
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
    average_traded_value: float | None
    taxonomy_name: str | None
    taxonomy_version: str | None


@dataclass(frozen=True, slots=True)
class SectorInputContext:
    """Classified active membership and policy-eligible feature inputs."""

    active_symbols: tuple[str, ...]
    sector_by_symbol: Mapping[str, str]
    taxonomy_by_symbol: Mapping[str, tuple[str | None, str | None]]
    member_counts: Mapping[str, int]
    feature_candidate_counts: Mapping[str, int]
    eligible_rows: tuple[FeatureRow, ...]
    security_type_excluded_symbols: tuple[str, ...]
    exclusion_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_symbols", tuple(self.active_symbols))
        object.__setattr__(
            self, "sector_by_symbol", MappingProxyType(dict(self.sector_by_symbol))
        )
        object.__setattr__(
            self,
            "taxonomy_by_symbol",
            MappingProxyType(dict(self.taxonomy_by_symbol)),
        )
        object.__setattr__(
            self, "member_counts", MappingProxyType(dict(self.member_counts))
        )
        object.__setattr__(
            self,
            "feature_candidate_counts",
            MappingProxyType(dict(self.feature_candidate_counts)),
        )
        object.__setattr__(self, "eligible_rows", tuple(self.eligible_rows))
        object.__setattr__(
            self,
            "security_type_excluded_symbols",
            tuple(self.security_type_excluded_symbols),
        )
        object.__setattr__(
            self, "exclusion_counts", MappingProxyType(dict(self.exclusion_counts))
        )

    @property
    def excluded_symbols(self) -> tuple[str, ...]:
        eligible_symbols = {row.symbol for row in self.eligible_rows}
        return tuple(
            symbol for symbol in self.active_symbols if symbol not in eligible_symbols
        )

    @property
    def unclassified_eligible_count(self) -> int:
        return sum(
            row.symbol not in self.sector_by_symbol for row in self.eligible_rows
        )

    @property
    def classified_eligible_count(self) -> int:
        return len(self.eligible_rows) - self.unclassified_eligible_count

    @property
    def metadata_coverage(self) -> float:
        """Legacy eligible-row metadata coverage."""
        return (
            self.classified_eligible_count / len(self.eligible_rows)
            if self.eligible_rows
            else 0.0
        )

    @property
    def active_metadata_coverage(self) -> float:
        return (
            len(self.sector_by_symbol) / len(self.active_symbols)
            if self.active_symbols
            else 0.0
        )

    @property
    def taxonomy_coverage(self) -> float:
        classified = tuple(self.sector_by_symbol)
        if not classified:
            return 0.0
        complete = sum(
            bool(name and version)
            for symbol in classified
            for name, version in (self.taxonomy_by_symbol.get(symbol, (None, None)),)
        )
        return complete / len(classified)

    @property
    def liquidity_candidate_count(self) -> int:
        return sum(self.feature_candidate_counts.values())

    @property
    def liquidity_coverage(self) -> float:
        return (
            len(self.eligible_rows) / self.liquidity_candidate_count
            if self.liquidity_candidate_count
            else 0.0
        )

    def metadata_coverage_for(self, policy: SectorStrengthPolicy) -> float:
        if policy is LEGACY_SECTOR_STRENGTH_POLICY:
            return self.metadata_coverage
        return self.active_metadata_coverage


@dataclass(frozen=True, slots=True)
class SectorAggregate:
    sector: str
    member_count: int
    feature_candidate_count: int
    rows: tuple[FeatureRow, ...]
    policy: SectorStrengthPolicy = LEGACY_SECTOR_STRENGTH_POLICY

    @property
    def eligible_count(self) -> int:
        return len(self.rows)

    @property
    def sector_coverage(self) -> float:
        return self.eligible_count / self.member_count if self.member_count else 0.0

    @property
    def liquidity_coverage(self) -> float:
        return (
            self.eligible_count / self.feature_candidate_count
            if self.feature_candidate_count
            else 0.0
        )

    def _robust_metric(self, name: str) -> tuple[float, int]:
        values = tuple(float(getattr(row, name)) for row in self.rows)
        winsorized, outlier_count = _winsorized(
            values,
            self.policy.winsor_lower_quantile,
            self.policy.winsor_upper_quantile,
        )
        return median(winsorized), outlier_count

    @property
    def median_return20(self) -> float:
        return self._robust_metric("return20")[0]

    @property
    def median_return60(self) -> float:
        return self._robust_metric("return60")[0]

    @property
    def median_rs20(self) -> float:
        return self._robust_metric("rs20")[0]

    @property
    def median_rs60(self) -> float:
        return self._robust_metric("rs60")[0]

    @property
    def outlier_adjustment_count(self) -> int:
        return sum(
            self._robust_metric(name)[1]
            for name in ("return20", "return60", "rs20", "rs60")
        )

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
    def concentration_ratio(self) -> float:
        values = tuple(
            row.average_traded_value
            for row in self.rows
            if row.average_traded_value is not None and row.average_traded_value > 0
        )
        total = sum(values)
        return max(values) / total if total else 0.0

    @property
    def score(self) -> float:
        weights = self.policy.score_weights
        leadership_share = self.leadership_count / self.eligible_count
        return (
            weights.relative_strength20 * self.median_rs20
            + weights.return20 * self.median_return20
            + weights.pct_above_ma20 * (self.pct_above_ma20 - 0.50)
            + weights.pct_above_ma50 * (self.pct_above_ma50 - 0.50)
            + weights.leadership_share * leadership_share
        )

    @property
    def rotation(self) -> str:
        if self.median_rs20 > 0 and self.median_rs20 > self.median_rs60:
            return "IMPROVING"
        if self.median_rs20 < 0 and self.median_rs20 < self.median_rs60:
            return "WEAKENING"
        return "STABLE"


def load_sector_input_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    policy: SectorStrengthPolicy = LEGACY_SECTOR_STRENGTH_POLICY,
) -> SectorInputContext:
    """Load active membership and feature rows under a versioned policy."""
    membership_rows: list[
        tuple[
            str,
            str | None,
            str | None,
            str | None,
            str | None,
        ]
    ] = conn.execute(
        """
        SELECT symbol, COALESCE(NULLIF(sector_name, ''), sector), security_type,
               taxonomy_name, taxonomy_version
        FROM symbol_master
        WHERE is_active = TRUE
          AND COALESCE(lifecycle_status, 'ACTIVE') = 'ACTIVE'
        ORDER BY symbol
        """
    ).fetchall()

    active_symbols: list[str] = []
    sector_by_symbol: dict[str, str] = {}
    taxonomy_by_symbol: dict[str, tuple[str | None, str | None]] = {}
    security_type_excluded_symbols: list[str] = []
    for (
        symbol,
        sector,
        security_type,
        taxonomy_name,
        taxonomy_version,
    ) in membership_rows:
        if not _security_type_allowed(security_type, policy):
            security_type_excluded_symbols.append(symbol)
            continue
        active_symbols.append(symbol)
        normalized_sector = sector.strip() if sector else ""
        if normalized_sector:
            sector_by_symbol[symbol] = normalized_sector
            taxonomy_by_symbol[symbol] = (
                taxonomy_name.strip() if taxonomy_name else None,
                taxonomy_version.strip() if taxonomy_version else None,
            )

    member_counts: defaultdict[str, int] = defaultdict(int)
    for sector in sector_by_symbol.values():
        member_counts[sector] += 1

    feature_rows = {
        row[0]: row[1:]
        for row in conn.execute(
            """
            SELECT symbol, close, ma20, ma50, return_20d, return_60d,
                   rs_20d_vs_vnindex, rs_60d_vs_vnindex, volume_ma20,
                   as_of_bar_date, feature_data_status, feature_profile,
                   neutral_completeness, relative_strength_completeness
            FROM feature_snapshot
            WHERE date = ?
            ORDER BY symbol
            """,
            [as_of_date],
        ).fetchall()
    }

    feature_candidate_counts: defaultdict[str, int] = defaultdict(int)
    eligible_rows: list[FeatureRow] = []
    exclusion_counts: Counter[str] = Counter()
    for symbol in active_symbols:
        row = feature_rows.get(symbol)
        if row is None:
            exclusion_counts["MISSING_FEATURE"] += 1
            continue
        (
            close,
            ma20,
            ma50,
            return20,
            return60,
            rs20,
            rs60,
            volume_ma20,
            bar_date,
            feature_status,
            feature_profile,
            neutral_completeness,
            relative_strength_completeness,
        ) = row
        if feature_profile not in policy.allowed_feature_profiles:
            exclusion_counts["PROFILE_NOT_ALLOWED"] += 1
            continue
        if (
            neutral_completeness != "COMPLETE"
            or relative_strength_completeness != "COMPLETE"
        ):
            exclusion_counts["INCOMPLETE_FEATURE_PROFILE"] += 1
            continue
        if bar_date is None:
            exclusion_counts["MISSING_BAR_DATE"] += 1
            continue
        staleness_days = (as_of_date - _as_date(bar_date)).days
        if staleness_days < 0 or staleness_days > policy.maximum_staleness_days:
            exclusion_counts["STALE_FEATURE"] += 1
            continue
        if feature_status not in {"EXACT_DATE", "STALE_DATE"}:
            exclusion_counts["UNUSABLE_FEATURE_STATUS"] += 1
            continue
        if any(
            value is None
            for value in (close, ma20, ma50, return20, return60, rs20, rs60)
        ):
            exclusion_counts["MISSING_REQUIRED_VALUE"] += 1
            continue

        sector = sector_by_symbol.get(symbol)
        feature_candidate_counts[sector or "__UNCLASSIFIED__"] += 1
        average_traded_value = (
            float(close) * float(volume_ma20) if volume_ma20 is not None else None
        )
        if policy.minimum_average_traded_value > 0 and (
            average_traded_value is None
            or average_traded_value < policy.minimum_average_traded_value
        ):
            exclusion_counts["LOW_LIQUIDITY"] += 1
            continue

        taxonomy_name, taxonomy_version = taxonomy_by_symbol.get(symbol, (None, None))
        eligible_rows.append(
            FeatureRow(
                symbol=symbol,
                close=float(close),
                ma20=float(ma20),
                ma50=float(ma50),
                return20=float(return20),
                return60=float(return60),
                rs20=float(rs20),
                rs60=float(rs60),
                average_traded_value=average_traded_value,
                taxonomy_name=taxonomy_name,
                taxonomy_version=taxonomy_version,
            )
        )

    return SectorInputContext(
        active_symbols=tuple(active_symbols),
        sector_by_symbol=sector_by_symbol,
        taxonomy_by_symbol=taxonomy_by_symbol,
        member_counts=member_counts,
        feature_candidate_counts=feature_candidate_counts,
        eligible_rows=tuple(eligible_rows),
        security_type_excluded_symbols=tuple(security_type_excluded_symbols),
        exclusion_counts=dict(exclusion_counts),
    )


def aggregate_sector_context(
    context: SectorInputContext,
    *,
    policy: SectorStrengthPolicy = LEGACY_SECTOR_STRENGTH_POLICY,
) -> tuple[SectorAggregate, ...]:
    """Group eligible rows under source-sector active membership."""
    grouped: defaultdict[str, list[FeatureRow]] = defaultdict(list)
    for row in context.eligible_rows:
        sector = context.sector_by_symbol.get(row.symbol)
        if sector is not None:
            grouped[sector].append(row)
    return tuple(
        SectorAggregate(
            sector=sector,
            member_count=member_count,
            feature_candidate_count=context.feature_candidate_counts.get(sector, 0),
            rows=tuple(grouped[sector]),
            policy=policy,
        )
        for sector, member_count in sorted(context.member_counts.items())
    )
