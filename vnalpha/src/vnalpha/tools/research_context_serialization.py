from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)


def market_payload(
    snapshot: MarketRegimeSnapshot, requested_date: str | None, lookup: str
) -> dict[str, Any]:
    return {
        "requested_date": requested_date,
        "lookup": lookup,
        "snapshot": market_snapshot_data(snapshot),
        "as_of_date": snapshot.as_of_date.isoformat(),
        "methodology_version": snapshot.methodology_version,
        "freshness": {
            "benchmark_bar_date": snapshot.benchmark_bar_date.isoformat(),
            "generated_at": snapshot.generated_at.isoformat(),
        },
        "lineage": dict(snapshot.lineage),
        "quality": snapshot.quality,
        "caveats": list(snapshot.caveats),
    }


def sector_collection_payload(
    snapshots: Sequence[SectorStrengthSnapshot],
    requested_date: str | None,
    lookup: str,
) -> dict[str, Any]:
    first = snapshots[0]
    return {
        "requested_date": requested_date,
        "lookup": lookup,
        "snapshots": [sector_snapshot_data(snapshot) for snapshot in snapshots],
        "as_of_date": first.as_of_date.isoformat(),
        "methodology_version": first.methodology_version,
        "freshness": {"generated_at": first.generated_at.isoformat()},
        "lineage": dict(first.lineage),
        "quality": "COMPLETE"
        if all(snapshot.quality == "COMPLETE" for snapshot in snapshots)
        else "INCOMPLETE",
        "caveats": caveats(snapshots),
    }


def missing_payload(
    requested_date: str | None, lookup: str, caveat: str
) -> dict[str, Any]:
    return {
        "requested_date": requested_date,
        "lookup": lookup,
        "snapshot": None,
        "as_of_date": None,
        "methodology_version": None,
        "freshness": None,
        "lineage": {},
        "quality": "INSUFFICIENT_DATA",
        "caveats": [caveat],
    }


def caveats(snapshots: Sequence[SectorStrengthSnapshot]) -> list[str]:
    return list(
        dict.fromkeys(caveat for snapshot in snapshots for caveat in snapshot.caveats)
    )


def market_snapshot_data(snapshot: MarketRegimeSnapshot) -> dict[str, Any]:
    return {
        "as_of_date": snapshot.as_of_date.isoformat(),
        "benchmark_symbol": snapshot.benchmark_symbol,
        "benchmark_bar_date": snapshot.benchmark_bar_date.isoformat(),
        "close": snapshot.close,
        "ma20": snapshot.ma20,
        "ma50": snapshot.ma50,
        "ma50_slope": snapshot.ma50_slope,
        "return20": snapshot.return20,
        "return60": snapshot.return60,
        "volatility20": snapshot.volatility20,
        "breadth_active_count": snapshot.breadth_active_count,
        "breadth_eligible_count": snapshot.breadth_eligible_count,
        "breadth_excluded_count": snapshot.breadth_excluded_count,
        "breadth_coverage": snapshot.breadth_coverage,
        "pct_above_ma20": snapshot.pct_above_ma20,
        "pct_above_ma50": snapshot.pct_above_ma50,
        "pct_positive_return20": snapshot.pct_positive_return20,
        "regime": snapshot.regime,
        "trend": snapshot.trend,
        "volatility": snapshot.volatility,
        "quality": snapshot.quality,
        "caveats": list(snapshot.caveats),
        "lineage": dict(snapshot.lineage),
        "methodology_version": snapshot.methodology_version,
        "generated_at": snapshot.generated_at.isoformat(),
    }


def sector_snapshot_data(snapshot: SectorStrengthSnapshot) -> dict[str, Any]:
    return {
        "as_of_date": snapshot.as_of_date.isoformat(),
        "sector": snapshot.sector,
        "rank": snapshot.rank,
        "member_count": snapshot.member_count,
        "eligible_count": snapshot.eligible_count,
        "median_return20": snapshot.median_return20,
        "median_return60": snapshot.median_return60,
        "median_rs20_vs_vnindex": snapshot.median_rs20_vs_vnindex,
        "median_rs60_vs_vnindex": snapshot.median_rs60_vs_vnindex,
        "pct_above_ma20": snapshot.pct_above_ma20,
        "pct_above_ma50": snapshot.pct_above_ma50,
        "leadership_count": snapshot.leadership_count,
        "score": snapshot.score,
        "rotation": snapshot.rotation,
        "metadata_coverage": snapshot.metadata_coverage,
        "unclassified_count": snapshot.unclassified_count,
        "quality": snapshot.quality,
        "caveats": list(snapshot.caveats),
        "lineage": dict(snapshot.lineage),
        "methodology_version": snapshot.methodology_version,
        "generated_at": snapshot.generated_at.isoformat(),
    }
