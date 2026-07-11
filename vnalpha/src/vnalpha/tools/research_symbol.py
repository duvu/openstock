from __future__ import annotations

import duckdb

from vnalpha.commands.normalizers import normalize_date
from vnalpha.tools.lineage import get_symbol_lineage
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.quality import get_quality_status
from vnalpha.tools.research_context import get_market_regime, get_symbol_alignment
from vnalpha.tools.research_intelligence_common import (
    RESEARCH_TOOL_VERSION,
    dedupe,
    derived_levels,
    feature_snapshot,
    get_score,
    required_symbol,
    resolve_symbol_date,
    score_context,
    technical_context,
    tool_data,
    warnings,
)


def deep_symbol_analysis(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
) -> ToolOutput:
    """Compose a bounded, warehouse-grounded symbol research payload."""

    normalized_symbol = required_symbol(symbol)
    as_of_date = resolve_symbol_date(conn, normalized_symbol, date)
    score = get_score(conn, normalized_symbol, as_of_date)
    feature = feature_snapshot(conn, normalized_symbol, as_of_date)
    levels = derived_levels(conn, normalized_symbol, as_of_date)
    market = get_market_regime(conn, date=as_of_date)
    sector = get_symbol_alignment(conn, symbol=normalized_symbol, date=as_of_date)
    quality = get_quality_status(conn, symbol=normalized_symbol, date=as_of_date)
    lineage = get_symbol_lineage(conn, symbol=normalized_symbol, date=as_of_date)

    missing_data: list[str] = []
    if score is None:
        missing_data.append("candidate_score")
    if feature is None:
        missing_data.append("feature_snapshot")
    if not levels.get("bars_used"):
        missing_data.append("canonical_ohlcv")

    caveats = dedupe(
        [
            *warnings(market),
            *warnings(sector),
            *warnings(quality),
            *warnings(lineage),
            "Derived levels are descriptive ranges from persisted daily bars, not forecasts.",
            "Confidence reflects data completeness and evidence consistency only.",
        ]
    )
    status = "READY" if score is not None and feature is not None else "PARTIAL"
    if score is None and feature is None and not levels.get("bars_used"):
        status = "UNAVAILABLE"

    data = {
        "status": status,
        "symbol": normalized_symbol,
        "requested_date": normalize_date(date),
        "as_of_date": as_of_date,
        "score_context": score_context(score),
        "technical_context": technical_context(feature),
        "levels": levels,
        "market_context": tool_data(market),
        "sector_context": tool_data(sector),
        "quality": {
            "feature_data_status": (
                feature.get("feature_data_status") if feature else None
            ),
            "source_row_count": feature.get("source_row_count") if feature else None,
            "benchmark_row_count": (
                feature.get("benchmark_row_count") if feature else None
            ),
            "tool": tool_data(quality),
        },
        "freshness": {
            "as_of_bar_date": feature.get("as_of_bar_date") if feature else None,
            "benchmark_as_of_bar_date": (
                feature.get("benchmark_as_of_bar_date") if feature else None
            ),
            "feature_generated_at": (
                feature.get("feature_generated_at") if feature else None
            ),
        },
        "lineage": {
            "score": score.get("lineage_json") if score else None,
            "feature": feature.get("lineage_json") if feature else None,
            "tool": tool_data(lineage),
        },
        "artifact_refs": [
            f"candidate_score:{normalized_symbol}:{as_of_date}",
            f"feature_snapshot:{normalized_symbol}:{as_of_date}",
            f"canonical_ohlcv:{normalized_symbol}:<=:{as_of_date}",
        ],
        "methodology_version": RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": missing_data,
    }
    return ToolOutput(
        data=data,
        summary=(
            f"Structured research context for {normalized_symbol} "
            f"on {as_of_date} ({status})."
        ),
        warnings=caveats if status != "READY" else warnings(quality),
    )


__all__ = ["deep_symbol_analysis"]
