"""Deterministic persisted sector strength research snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Final

import duckdb

from vnalpha.observability.domain import log_sector_strength_built
from vnalpha.research_intelligence.models import SectorStrengthSnapshot
from vnalpha.research_intelligence.sector_context import (
    SectorInputContext,
    aggregate_sector_context,
    load_sector_input_context,
)
from vnalpha.warehouse.repositories import replace_sector_strength_snapshots

METHODOLOGY_VERSION: Final = "sector-strength-v1"
MINIMUM_SECTOR_MEMBERS: Final = 3


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


def _build_lineage(context: SectorInputContext) -> dict[str, str]:
    active_count = len(context.active_symbols)
    eligible_count = len(context.eligible_rows)
    excluded_symbols = context.excluded_symbols
    return {
        "input": "symbol_master,feature_snapshot",
        "active_symbol_count": str(active_count),
        "eligible_symbol_count": str(eligible_count),
        "excluded_symbol_count": str(len(excluded_symbols)),
        "classified_eligible_count": str(context.classified_eligible_count),
        "unclassified_count": str(context.unclassified_eligible_count),
        "metadata_coverage": ""
        if not eligible_count
        else str(context.metadata_coverage),
        "excluded_symbols": ",".join(excluded_symbols),
        "feature_data_freshness": "EXACT_DATE",
        "feature_bar_date_basis": "as_of_bar_date == as_of_date",
        "feature_usability_basis": "required_feature_values_nonnull",
        "methodology_version": METHODOLOGY_VERSION,
    }


def _build_caveats(
    context: SectorInputContext,
    rankable_sector_names: set[str],
) -> list[str]:
    aggregates = aggregate_sector_context(context)
    caveats = [
        f"{aggregate.sector} has {aggregate.eligible_count} eligible members; {MINIMUM_SECTOR_MEMBERS} required."
        for aggregate in aggregates
        if aggregate.sector not in rankable_sector_names
    ]
    if context.unclassified_eligible_count:
        caveats.append(
            f"{context.unclassified_eligible_count} eligible symbols lack nonblank sector metadata."
        )
    if context.excluded_symbols:
        caveats.append(
            f"{len(context.excluded_symbols)} active symbols lack usable exact-date features."
        )
    return caveats


def _quality_for(context: SectorInputContext, rankable_count: int) -> str:
    if not rankable_count:
        return "INSUFFICIENT_DATA"
    if context.unclassified_eligible_count:
        return "PARTIAL_METADATA"
    if context.excluded_symbols:
        return "INCOMPLETE"
    return "OK"


def build_sector_strength(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    generated_at: datetime | None = None,
) -> SectorStrengthBuildResult:
    """Build and replace rankable exact-date sector research snapshots."""
    context = load_sector_input_context(conn, as_of_date)
    aggregates = aggregate_sector_context(context)
    rankable = tuple(
        aggregate
        for aggregate in aggregates
        if aggregate.eligible_count >= MINIMUM_SECTOR_MEMBERS
    )
    rankable_names = {aggregate.sector for aggregate in rankable}
    caveats = _build_caveats(context, rankable_names)
    lineage = _build_lineage(context)
    quality = _quality_for(context, len(rankable))
    if not rankable:
        caveats.append(
            f"No sector has {MINIMUM_SECTOR_MEMBERS} classified eligible members."
        )
        replace_sector_strength_snapshots(conn, as_of_date, ())
        result = SectorStrengthBuildResult((), quality, tuple(caveats), lineage)
        log_sector_strength_built(
            as_of_date.isoformat(),
            len(result.snapshots),
            context.metadata_coverage,
            context.unclassified_eligible_count,
            result.quality,
            METHODOLOGY_VERSION,
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
    snapshots = tuple(
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
            metadata_coverage=context.metadata_coverage,
            unclassified_count=context.unclassified_eligible_count,
            quality=quality,
            caveats=tuple(caveats),
            lineage=lineage,
            methodology_version=METHODOLOGY_VERSION,
            generated_at=timestamp,
        )
        for rank, aggregate in enumerate(ordered, start=1)
    )
    replace_sector_strength_snapshots(conn, as_of_date, snapshots)
    result = SectorStrengthBuildResult(snapshots, quality, tuple(caveats), lineage)
    log_sector_strength_built(
        as_of_date.isoformat(),
        len(result.snapshots),
        context.metadata_coverage,
        context.unclassified_eligible_count,
        result.quality,
        METHODOLOGY_VERSION,
    )
    return result
