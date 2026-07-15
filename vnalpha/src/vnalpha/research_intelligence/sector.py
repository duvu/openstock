"""Deterministic, versioned sector-strength research snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Final

import duckdb

from vnalpha.observability.domain import log_sector_strength_built
from vnalpha.research_intelligence.models import SectorStrengthSnapshot
from vnalpha.research_intelligence.policy import (
    LEGACY_SECTOR_STRENGTH_POLICY,
    PRODUCTION_SECTOR_STRENGTH_POLICY,
    SectorStrengthPolicy,
)
from vnalpha.research_intelligence.sector_context import (
    SectorAggregate,
    SectorInputContext,
    aggregate_sector_context,
    load_sector_input_context,
)
from vnalpha.warehouse.repositories import replace_sector_strength_snapshots

LEGACY_METHODOLOGY_VERSION: Final = LEGACY_SECTOR_STRENGTH_POLICY.methodology_version
METHODOLOGY_VERSION: Final = PRODUCTION_SECTOR_STRENGTH_POLICY.methodology_version
MINIMUM_SECTOR_MEMBERS: Final = LEGACY_SECTOR_STRENGTH_POLICY.minimum_sector_members


@dataclass(frozen=True, slots=True)
class SectorStrengthBuildResult:
    """The persisted sector snapshots and research-data quality context."""

    snapshots: tuple[SectorStrengthSnapshot, ...]
    quality: str
    caveats: tuple[str, ...]
    lineage: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshots", tuple(self.snapshots))
        object.__setattr__(self, "caveats", tuple(self.caveats))
        object.__setattr__(self, "lineage", MappingProxyType(dict(self.lineage)))


def _unclassified_count(
    context: SectorInputContext, policy: SectorStrengthPolicy
) -> int:
    if policy is LEGACY_SECTOR_STRENGTH_POLICY:
        return context.unclassified_eligible_count
    return len(context.active_symbols) - len(context.sector_by_symbol)


def _build_lineage(
    context: SectorInputContext, policy: SectorStrengthPolicy
) -> dict[str, str]:
    active_count = len(context.active_symbols)
    eligible_count = len(context.eligible_rows)
    excluded_symbols = context.excluded_symbols
    weights = policy.score_weights
    return {
        "input": "symbol_master,feature_snapshot",
        "active_symbol_count": str(active_count),
        "eligible_symbol_count": str(eligible_count),
        "excluded_symbol_count": str(len(excluded_symbols)),
        "classified_eligible_count": str(context.classified_eligible_count),
        "unclassified_count": str(_unclassified_count(context, policy)),
        "metadata_coverage": str(context.metadata_coverage_for(policy)),
        "eligible_metadata_coverage": str(context.metadata_coverage),
        "active_metadata_coverage": str(context.active_metadata_coverage),
        "taxonomy_coverage": str(context.taxonomy_coverage),
        "liquidity_candidate_count": str(context.liquidity_candidate_count),
        "liquidity_coverage": str(context.liquidity_coverage),
        "excluded_symbols": ",".join(excluded_symbols),
        "security_type_excluded_symbols": ",".join(
            context.security_type_excluded_symbols
        ),
        "exclusion_counts": ",".join(
            f"{reason}:{count}"
            for reason, count in sorted(context.exclusion_counts.items())
        ),
        "feature_data_freshness": "EXACT_DATE"
        if policy.maximum_staleness_days == 0
        else f"MAX_STALENESS_{policy.maximum_staleness_days}_DAYS",
        "feature_bar_date_basis": (
            "as_of_bar_date == as_of_date"
            if policy.maximum_staleness_days == 0
            else "as_of_bar_date <= as_of_date"
        ),
        "feature_usability_basis": "profile,completeness,security_type,liquidity",
        "policy_minimum_sector_members": str(policy.minimum_sector_members),
        "policy_minimum_eligible_members": str(policy.minimum_eligible_members),
        "policy_minimum_sector_coverage": str(policy.minimum_sector_coverage),
        "policy_minimum_metadata_coverage": str(policy.minimum_metadata_coverage),
        "policy_minimum_taxonomy_coverage": str(policy.minimum_taxonomy_coverage),
        "policy_minimum_liquidity_coverage": str(policy.minimum_liquidity_coverage),
        "policy_minimum_average_traded_value": str(policy.minimum_average_traded_value),
        "policy_allowed_feature_profiles": ",".join(policy.allowed_feature_profiles),
        "policy_allowed_security_types": ",".join(policy.allowed_security_types),
        "policy_winsor_quantiles": (
            f"{policy.winsor_lower_quantile},{policy.winsor_upper_quantile}"
        ),
        "policy_concentration_warning_threshold": str(
            policy.concentration_warning_threshold
        ),
        "score_weights": (
            f"rs20={weights.relative_strength20},return20={weights.return20},"
            f"above_ma20={weights.pct_above_ma20},"
            f"above_ma50={weights.pct_above_ma50},"
            f"leadership={weights.leadership_share}"
        ),
        "methodology_version": policy.methodology_version,
    }


def _rankability_reasons(
    aggregate: SectorAggregate, policy: SectorStrengthPolicy
) -> tuple[str, ...]:
    reasons: list[str] = []
    if aggregate.member_count < policy.minimum_sector_members:
        reasons.append(
            f"{aggregate.sector} has {aggregate.member_count} active members; "
            f"{policy.minimum_sector_members} required."
        )
    if aggregate.eligible_count < policy.minimum_eligible_members:
        reasons.append(
            f"{aggregate.sector} has {aggregate.eligible_count} eligible members; "
            f"{policy.minimum_eligible_members} required."
        )
    if aggregate.sector_coverage < policy.minimum_sector_coverage:
        reasons.append(
            f"{aggregate.sector} feature coverage is {aggregate.sector_coverage:.3f}; "
            f"{policy.minimum_sector_coverage:.3f} required."
        )
    if aggregate.liquidity_coverage < policy.minimum_liquidity_coverage:
        reasons.append(
            f"{aggregate.sector} liquidity coverage is "
            f"{aggregate.liquidity_coverage:.3f}; "
            f"{policy.minimum_liquidity_coverage:.3f} required."
        )
    return tuple(reasons)


def _quality_for(
    context: SectorInputContext,
    rankable_count: int,
    policy: SectorStrengthPolicy,
) -> str:
    if not rankable_count:
        return "INSUFFICIENT_DATA"
    if policy is LEGACY_SECTOR_STRENGTH_POLICY:
        if context.unclassified_eligible_count:
            return "PARTIAL_METADATA"
        if context.excluded_symbols:
            return "INCOMPLETE"
        return "OK"
    if (
        context.metadata_coverage_for(policy) < policy.minimum_metadata_coverage
        or context.taxonomy_coverage < policy.minimum_taxonomy_coverage
    ):
        return "PARTIAL_METADATA"
    if context.liquidity_coverage < policy.minimum_liquidity_coverage:
        return "INCOMPLETE"
    return "OK"


def _global_caveats(
    context: SectorInputContext,
    policy: SectorStrengthPolicy,
) -> list[str]:
    caveats: list[str] = []
    metadata_coverage = context.metadata_coverage_for(policy)
    if metadata_coverage < policy.minimum_metadata_coverage:
        caveats.append(
            f"Metadata coverage is {metadata_coverage:.3f}; "
            f"{policy.minimum_metadata_coverage:.3f} required."
        )
    if context.taxonomy_coverage < policy.minimum_taxonomy_coverage:
        caveats.append(
            f"Taxonomy coverage is {context.taxonomy_coverage:.3f}; "
            f"{policy.minimum_taxonomy_coverage:.3f} required."
        )
    if context.liquidity_coverage < policy.minimum_liquidity_coverage:
        caveats.append(
            f"Global liquidity coverage is {context.liquidity_coverage:.3f}; "
            f"{policy.minimum_liquidity_coverage:.3f} required."
        )
    if _unclassified_count(context, policy):
        if policy is LEGACY_SECTOR_STRENGTH_POLICY:
            caveats.append(
                f"{_unclassified_count(context, policy)} eligible symbols "
                "lack nonblank sector metadata."
            )
        else:
            caveats.append(
                f"{_unclassified_count(context, policy)} policy-eligible symbols "
                "lack nonblank sector metadata."
            )
    if context.excluded_symbols:
        if policy is LEGACY_SECTOR_STRENGTH_POLICY:
            caveats.append(
                f"{len(context.excluded_symbols)} active symbols lack usable exact-date features."
            )
        else:
            caveats.append(
                f"{len(context.excluded_symbols)} active policy-universe symbols "
                "lack usable feature or liquidity evidence."
            )
    return caveats


def _snapshot_lineage(
    global_lineage: Mapping[str, str], aggregate: SectorAggregate
) -> dict[str, str]:
    taxonomy_pairs = sorted(
        {
            (row.taxonomy_name or "", row.taxonomy_version or "")
            for row in aggregate.rows
        }
    )
    lineage = dict(global_lineage)
    lineage.update(
        {
            "sector": aggregate.sector,
            "sector_member_count": str(aggregate.member_count),
            "sector_feature_candidate_count": str(aggregate.feature_candidate_count),
            "sector_eligible_count": str(aggregate.eligible_count),
            "sector_coverage": str(aggregate.sector_coverage),
            "sector_liquidity_coverage": str(aggregate.liquidity_coverage),
            "sector_concentration_ratio": str(aggregate.concentration_ratio),
            "sector_outlier_adjustment_count": str(aggregate.outlier_adjustment_count),
            "taxonomy_versions": ",".join(
                f"{name}:{version}" for name, version in taxonomy_pairs
            ),
        }
    )
    return lineage


def build_sector_strength(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    generated_at: datetime | None = None,
    policy: SectorStrengthPolicy = PRODUCTION_SECTOR_STRENGTH_POLICY,
) -> SectorStrengthBuildResult:
    """Build and replace sector snapshots under a versioned policy."""
    context = load_sector_input_context(conn, as_of_date, policy=policy)
    aggregates = aggregate_sector_context(context, policy=policy)
    rankability = {
        aggregate.sector: _rankability_reasons(aggregate, policy)
        for aggregate in aggregates
    }
    rankable = tuple(
        aggregate for aggregate in aggregates if not rankability[aggregate.sector]
    )
    caveats = _global_caveats(context, policy)
    for aggregate in aggregates:
        caveats.extend(rankability[aggregate.sector])
    lineage = _build_lineage(context, policy)
    quality = _quality_for(context, len(rankable), policy)
    if not rankable:
        caveats.append(
            f"No sector has {policy.minimum_eligible_members} classified eligible members."
            if policy is LEGACY_SECTOR_STRENGTH_POLICY
            else "No sector satisfies the production rankability policy."
        )
        replace_sector_strength_snapshots(conn, as_of_date, ())
        result = SectorStrengthBuildResult((), quality, tuple(caveats), lineage)
        log_sector_strength_built(
            as_of_date.isoformat(),
            0,
            context.metadata_coverage_for(policy),
            _unclassified_count(context, policy),
            result.quality,
            policy.methodology_version,
        )
        return result

    ordered = sorted(
        rankable,
        key=lambda aggregate: (
            -aggregate.score,
            -aggregate.median_rs20,
            aggregate.sector,
        ),
    )
    timestamp = generated_at or datetime.now(timezone.utc)
    snapshots: list[SectorStrengthSnapshot] = []
    for rank, aggregate in enumerate(ordered, start=1):
        snapshot_caveats = list(caveats)
        if aggregate.outlier_adjustment_count:
            snapshot_caveats.append(
                f"{aggregate.sector} winsorized "
                f"{aggregate.outlier_adjustment_count} metric observations."
            )
        if aggregate.concentration_ratio > policy.concentration_warning_threshold:
            snapshot_caveats.append(
                f"{aggregate.sector} liquidity concentration is "
                f"{aggregate.concentration_ratio:.3f}; policy warning threshold is "
                f"{policy.concentration_warning_threshold:.3f}."
            )
        snapshots.append(
            SectorStrengthSnapshot(
                as_of_date=as_of_date,
                sector=aggregate.sector,
                rank=rank,
                member_count=aggregate.member_count,
                eligible_count=aggregate.eligible_count,
                median_return20=aggregate.median_return20,
                median_return60=aggregate.median_return60,
                median_rs20_vs_vnindex=aggregate.median_rs20,
                median_rs60_vs_vnindex=aggregate.median_rs60,
                pct_above_ma20=aggregate.pct_above_ma20,
                pct_above_ma50=aggregate.pct_above_ma50,
                leadership_count=aggregate.leadership_count,
                score=aggregate.score,
                rotation=aggregate.rotation,
                metadata_coverage=context.metadata_coverage_for(policy),
                unclassified_count=_unclassified_count(context, policy),
                quality=quality,
                caveats=tuple(snapshot_caveats),
                lineage=_snapshot_lineage(lineage, aggregate),
                methodology_version=policy.methodology_version,
                generated_at=timestamp,
            )
        )

    persisted = tuple(snapshots)
    replace_sector_strength_snapshots(conn, as_of_date, persisted)
    result = SectorStrengthBuildResult(persisted, quality, tuple(caveats), lineage)
    log_sector_strength_built(
        as_of_date.isoformat(),
        len(result.snapshots),
        context.metadata_coverage_for(policy),
        _unclassified_count(context, policy),
        result.quality,
        policy.methodology_version,
    )
    return result
