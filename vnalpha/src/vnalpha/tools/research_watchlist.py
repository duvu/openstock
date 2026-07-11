from __future__ import annotations

from collections import Counter
from typing import Any

import duckdb

from vnalpha.commands.normalizers import normalize_setup_type
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_intelligence_common import (
    RESEARCH_TOOL_VERSION,
    bounded_int,
    clamp,
    load_watchlist_rows,
    number,
    resolve_watchlist_date,
    shortlist_reasons,
    watchlist_identity,
)


def summarize_watchlist_deep(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
) -> ToolOutput:
    """Summarize persisted watchlist structure without free-form inference."""

    as_of_date = resolve_watchlist_date(conn, date)
    rows = load_watchlist_rows(conn, as_of_date)
    if not rows:
        caveat = f"No persisted watchlist rows are available for {as_of_date}."
        return ToolOutput(
            data={
                "status": "UNAVAILABLE",
                "as_of_date": as_of_date,
                "candidate_count": 0,
                "class_distribution": {},
                "setup_distribution": {},
                "sector_clusters": {},
                "research_focus": {},
                "quality": "INSUFFICIENT_DATA",
                "artifact_refs": [f"daily_watchlist:{as_of_date}"],
                "methodology_version": RESEARCH_TOOL_VERSION,
                "caveats": [caveat],
                "missing_data": ["daily_watchlist"],
            },
            summary="No persisted watchlist is available for deep synthesis.",
            warnings=[caveat],
        )

    class_distribution = Counter(
        str(row.get("candidate_class") or "UNCLASSIFIED") for row in rows
    )
    setup_distribution = Counter(
        str(row.get("setup_type") or "UNCLASSIFIED") for row in rows
    )
    sector_clusters = Counter(
        str(row.get("sector") or "UNCLASSIFIED") for row in rows
    )
    high_rs = sorted(
        (row for row in rows if row.get("rs_20d_vs_vnindex") is not None),
        key=lambda row: float(row["rs_20d_vs_vnindex"]),
        reverse=True,
    )[:10]
    near_confirmation = [
        row
        for row in rows
        if number(row.get("breakout_score")) >= 0.65
        and -0.08 <= number(row.get("distance_to_52w_high"), -1.0) <= 0.03
    ][:10]
    extended = [
        row for row in rows if number(row.get("distance_to_ma20")) > 0.10
    ][:10]
    risk_flagged = [row for row in rows if row.get("risk_flags")][:15]
    low_quality = [
        row
        for row in rows
        if str(row.get("feature_data_status") or "").upper()
        not in {"", "READY", "COMPLETE"}
    ][:15]
    caveats = [
        "Watchlist order is a persisted screening result and requires current-data review.",
        "Sector grouping depends on available symbol metadata.",
    ]
    missing_data: list[str] = []
    if sector_clusters.get("UNCLASSIFIED"):
        missing_data.append("sector metadata for some symbols")
        caveats.append("Some symbols have no persisted sector classification.")

    data = {
        "status": "READY" if not missing_data else "PARTIAL",
        "as_of_date": as_of_date,
        "candidate_count": len(rows),
        "class_distribution": dict(class_distribution),
        "setup_distribution": dict(setup_distribution),
        "sector_clusters": dict(sector_clusters),
        "top_ranked": [watchlist_identity(row) for row in rows[:10]],
        "research_focus": {
            "high_relative_strength": [
                watchlist_identity(row) for row in high_rs
            ],
            "near_confirmation": [
                watchlist_identity(row) for row in near_confirmation
            ],
            "extendedness_review": [
                watchlist_identity(row) for row in extended
            ],
            "risk_flagged": [watchlist_identity(row) for row in risk_flagged],
            "low_data_quality": [
                watchlist_identity(row) for row in low_quality
            ],
        },
        "quality": "PARTIAL" if missing_data or low_quality else "READY",
        "freshness": {"watchlist_date": as_of_date},
        "artifact_refs": [
            f"daily_watchlist:{as_of_date}",
            f"candidate_score:{as_of_date}",
            f"feature_snapshot:{as_of_date}",
        ],
        "methodology_version": RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": missing_data,
    }
    return ToolOutput(
        data=data,
        summary=(
            f"Deep watchlist synthesis for {len(rows)} candidates on {as_of_date}."
        ),
        warnings=caveats if missing_data or low_quality else [],
    )


def generate_shortlist(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
    limit: int = 5,
    setup: str | None = None,
    sector: str | None = None,
) -> ToolOutput:
    """Build an explainable research-priority shortlist from persisted artifacts."""

    as_of_date = resolve_watchlist_date(conn, date)
    resolved_limit = bounded_int(limit, name="limit", lower=1, upper=30)
    setup_filter = normalize_setup_type(setup) if setup else None
    sector_filter = sector.strip().casefold() if sector else None
    rows = load_watchlist_rows(conn, as_of_date)
    if setup_filter:
        rows = [row for row in rows if row.get("setup_type") == setup_filter]
    if sector_filter:
        rows = [
            row
            for row in rows
            if str(row.get("sector") or "").strip().casefold() == sector_filter
        ]

    ranked = [_rank_candidate(row, as_of_date) for row in rows]
    ranked.sort(
        key=lambda item: (
            -float(item["shortlist_score"]),
            int(item["watchlist_rank"] or 9999),
        )
    )
    candidates = [
        {**item, "research_rank": index}
        for index, item in enumerate(ranked[:resolved_limit], start=1)
    ]
    caveats = [
        "This shortlist prioritizes research review; it is not action guidance.",
        "The formula is deterministic and uses persisted score, risk, and feature quality.",
        "Human review and fresh data remain required.",
    ]
    missing_data = [] if candidates else ["matching watchlist candidates"]
    data = {
        "status": "READY" if candidates else "UNAVAILABLE",
        "as_of_date": as_of_date,
        "methodology": {
            "version": RESEARCH_TOOL_VERSION,
            "components": [
                "candidate_score",
                "trend_score",
                "relative_strength_score",
                "risk_quality_score",
                "risk penalty",
                "extendedness penalty",
                "data quality penalty",
            ],
            "limit": resolved_limit,
            "setup_filter": setup_filter,
            "sector_filter": sector,
        },
        "candidates": candidates,
        "artifact_refs": [f"daily_watchlist:{as_of_date}"],
        "freshness": {"watchlist_date": as_of_date},
        "caveats": caveats,
        "missing_data": missing_data,
    }
    return ToolOutput(
        data=data,
        summary=(
            f"Generated {len(candidates)} research-priority candidates "
            f"for {as_of_date}."
        ),
        warnings=caveats if not candidates else [],
    )


def _rank_candidate(row: dict[str, Any], as_of_date: str) -> dict[str, Any]:
    risk_flags = list(row.get("risk_flags") or [])
    risk_penalty = min(0.20, 0.04 * len(risk_flags))
    extendedness = max(0.0, number(row.get("distance_to_ma20")) - 0.08)
    extendedness_penalty = min(0.15, extendedness)
    quality_penalty = (
        0.08
        if str(row.get("feature_data_status") or "").upper()
        not in {"", "READY", "COMPLETE"}
        else 0.0
    )
    shortlist_score = clamp(
        0.65 * number(row.get("score"))
        + 0.10 * number(row.get("trend_score"))
        + 0.10 * number(row.get("relative_strength_score"))
        + 0.15 * number(row.get("risk_quality_score"))
        - risk_penalty
        - extendedness_penalty
        - quality_penalty
    )
    risks = list(risk_flags)
    if extendedness_penalty:
        risks.append("extendedness requires review")
    if quality_penalty:
        risks.append("data quality is incomplete")
    return {
        "symbol": row.get("symbol"),
        "watchlist_rank": row.get("rank"),
        "candidate_score": row.get("score"),
        "shortlist_score": round(shortlist_score, 6),
        "candidate_class": row.get("candidate_class"),
        "setup_type": row.get("setup_type"),
        "sector": row.get("sector"),
        "why_shortlisted": shortlist_reasons(row),
        "risks_to_review": risks,
        "confirmation_needed": (
            "Review current price/volume confirmation and data freshness "
            "before forming a conclusion."
        ),
        "artifact_refs": [
            f"candidate_score:{row.get('symbol')}:{as_of_date}",
            f"daily_watchlist:{row.get('symbol')}:{as_of_date}",
        ],
    }


__all__ = ["generate_shortlist", "summarize_watchlist_deep"]
