"""Deterministic, read-only research-intelligence tools.

These tools compose persisted warehouse artifacts. They never expose raw SQL,
filesystem access, broker/account state, or unrestricted code execution to the
assistant. Missing upstream artifacts are reported explicitly instead of being
inferred or fabricated.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date as calendar_date
from typing import Any

import duckdb

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.data_availability.deep_readiness_models import ContextRequirement
from vnalpha.research_models import ResearchModelsRepository
from vnalpha.research_models.scenario_plan import ScenarioPlanBuilder
from vnalpha.research_models.scenario_policy import validate_research_scenario_payload
from vnalpha.tools.artifact_references import ArtifactReferenceBuilder
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_context import (
    get_market_regime,
    get_sector_strength,
    get_symbol_alignment,
)
from vnalpha.warehouse.repositories import (
    get_candidate_score,
    get_watchlist_rich,
)

_RESEARCH_ONLY_CAVEAT = (
    "Research-only conditional context; this is not a recommendation."
)


def deep_symbol_analysis(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
    *,
    market_regime_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    sector_strength_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
) -> ToolOutput:
    """Return a bounded deep-symbol research payload from persisted artifacts."""
    normalized_symbol = _require_symbol(symbol)
    target_date = _resolve_symbol_date(conn, normalized_symbol, date)
    if target_date is None:
        missing = (
            f"No persisted market artifacts are available for {normalized_symbol}."
        )
        return ToolOutput(
            data=_missing_payload(
                "analysis.deep_symbol",
                normalized_symbol,
                date,
                ["symbol_history"],
                missing,
            ),
            summary=missing,
            warnings=[missing],
        )

    score = get_candidate_score(conn, normalized_symbol, target_date)
    feature = _feature_snapshot(conn, normalized_symbol, target_date)
    bars = _recent_bars(conn, normalized_symbol, target_date, limit=60)
    symbol_metadata = _symbol_metadata(conn, normalized_symbol)
    market = get_market_regime(conn, target_date)
    sector = get_symbol_alignment(conn, normalized_symbol, target_date)
    quality = _latest_quality(conn, normalized_symbol, target_date)
    levels = _level_context(bars, feature)

    missing_data: list[str] = []
    optional_missing_data: list[str] = []
    caveats: list[str] = []
    artifact_refs = ArtifactReferenceBuilder()
    if score is None:
        missing_data.append("candidate_score")
        caveats.append(
            f"No candidate score exists for {normalized_symbol} on {target_date}."
        )
    else:
        artifact_refs.add_if_present(
            "candidate_score", f"{normalized_symbol}:{target_date}", True
        )
    if feature is None:
        missing_data.append("feature_snapshot")
        caveats.append(
            f"No feature snapshot exists for {normalized_symbol} on {target_date}."
        )
    else:
        artifact_refs.add_if_present(
            "feature_snapshot", f"{normalized_symbol}:{target_date}", True
        )
    if not bars:
        missing_data.append("canonical_ohlcv")
        caveats.append(
            f"No canonical OHLCV exists for {normalized_symbol} through {target_date}."
        )
    else:
        artifact_refs.add_if_present(
            "canonical_ohlcv", f"{normalized_symbol}:through:{target_date}", True
        )

    if market_regime_requirement is not ContextRequirement.NOT_REQUESTED:
        caveats.extend(_tool_warnings(market))
    if sector_strength_requirement is not ContextRequirement.NOT_REQUESTED:
        caveats.extend(_tool_warnings(sector))
    market_data = _tool_data(market)
    sector_data = _tool_data(sector)
    market_date = market_data.get("as_of_date")
    artifact_refs.add_if_present(
        "market_regime_snapshot",
        str(market_date),
        bool(market_date and market_data.get("snapshot") is not None),
    )
    market_snapshot_present = bool(
        market_date and market_data.get("snapshot") is not None
    )
    if (
        market_regime_requirement is ContextRequirement.REQUIRED
        and not market_snapshot_present
    ):
        missing_data.append("market_regime_snapshot")
        caveats.append(
            "Required market regime context was unavailable for the resolved date."
        )
    elif (
        market_regime_requirement is ContextRequirement.OPTIONAL
        and not market_snapshot_present
    ):
        optional_missing_data.append("market_regime_snapshot")
    sector_date = sector_data.get("as_of_date")
    sector_name = sector_data.get("sector") or normalized_symbol
    sector_snapshot_present = bool(
        sector_date and sector_data.get("snapshot") is not None
    )
    artifact_refs.add_if_present(
        "sector_strength_snapshot",
        f"{sector_name}:{sector_date}",
        sector_snapshot_present,
    )
    if (
        sector_strength_requirement is ContextRequirement.REQUIRED
        and not sector_snapshot_present
    ):
        missing_data.append("sector_strength_snapshot")
        caveats.append(
            "No persisted sector strength snapshot was available for "
            f"{normalized_symbol} on or before {target_date}."
        )
    elif (
        sector_strength_requirement is ContextRequirement.OPTIONAL
        and not sector_snapshot_present
    ):
        optional_missing_data.append("sector_strength_snapshot")

    data = {
        "tool": "analysis.deep_symbol",
        "available": bool(score or feature or bars),
        "symbol": normalized_symbol,
        "requested_date": date,
        "as_of_date": target_date,
        "symbol_metadata": symbol_metadata,
        "candidate": score,
        "feature_context": feature,
        "levels": levels,
        "market_context": market_data,
        "sector_context": sector_data,
        "quality": quality,
        "freshness": {
            "price_bar_date": bars[0]["date"] if bars else None,
            "feature_generated_at": feature.get("feature_generated_at")
            if feature
            else None,
            "score_generated_at": (score or {})
            .get("lineage_json", {})
            .get("generated_at"),
        },
        "lineage": {
            "candidate_score": (score or {}).get("lineage_json", {}),
            "feature_snapshot": (feature or {}).get("lineage", {}),
            "market_context": market_data.get("lineage", {})
            if isinstance(market_data, dict)
            else {},
            "sector_context": sector_data.get("lineage", {})
            if isinstance(sector_data, dict)
            else {},
        },
        "artifact_refs": artifact_refs.build(),
        "context_requirements": {
            "market_regime": market_regime_requirement.value,
            "sector_strength": sector_strength_requirement.value,
        },
        "missing_data": missing_data,
        "optional_missing_data": optional_missing_data,
        "caveats": list(dict.fromkeys(caveats)),
        "policy": {"mode": "research_only", "disclaimer": _RESEARCH_ONLY_CAVEAT},
    }
    warnings = list(dict.fromkeys(caveats))
    return ToolOutput(
        data=data,
        summary=(
            f"Deep persisted research context for {normalized_symbol} as of {target_date}; "
            f"{len(missing_data)} required artifact(s) missing."
        ),
        warnings=warnings,
    )


def summarize_watchlist_deep(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
    top: int | None = None,
) -> ToolOutput:
    """Aggregate a persisted watchlist into bounded research context."""
    target_date = _resolve_watchlist_date(conn, date)
    limit = _normalize_positive_int(top, default=10, maximum=50)
    if target_date is None:
        caveat = "No persisted daily watchlist is available."
        return ToolOutput(
            data=_missing_payload(
                "watchlist.summarize_deep", None, date, ["daily_watchlist"], caveat
            ),
            summary=caveat,
            warnings=[caveat],
        )

    rows = get_watchlist_rich(conn, target_date)
    sectors = _symbol_sector_map(conn, [row["symbol"] for row in rows])
    market = get_market_regime(conn, target_date)
    if not rows:
        caveat = f"The persisted watchlist for {target_date} is empty."
        data = _missing_payload(
            "watchlist.summarize_deep", None, target_date, ["daily_watchlist"], caveat
        )
        data["market_context"] = _tool_data(market)
        return ToolOutput(data=data, summary=caveat, warnings=[caveat])

    class_counts = Counter(str(row.get("candidate_class") or "UNKNOWN") for row in rows)
    setup_counts = Counter(str(row.get("setup_type") or "UNCLASSIFIED") for row in rows)
    sector_counts = Counter(
        sectors.get(row["symbol"]) or "UNCLASSIFIED" for row in rows
    )
    quality_counts = Counter(
        str(row.get("data_quality_status") or "unknown") for row in rows
    )
    risk_counts: Counter[str] = Counter()
    for row in rows:
        risk_counts.update(_risk_flags(row.get("risk_flags_json")))

    top_candidates = [
        {
            "rank": row.get("rank"),
            "symbol": row.get("symbol"),
            "score": row.get("score"),
            "candidate_class": row.get("candidate_class"),
            "setup_type": row.get("setup_type"),
            "sector": sectors.get(row["symbol"]),
            "risk_flags": _risk_flags(row.get("risk_flags_json")),
            "data_quality_status": row.get("data_quality_status"),
        }
        for row in rows[:limit]
    ]
    market_data = _tool_data(market)
    caveats = _tool_warnings(market)
    artifact_refs = ArtifactReferenceBuilder()
    artifact_refs.add_if_present("daily_watchlist", target_date, bool(rows))
    data = {
        "tool": "watchlist.summarize_deep",
        "available": True,
        "requested_date": date,
        "as_of_date": target_date,
        "watchlist_size": len(rows),
        "candidate_class_distribution": dict(class_counts),
        "setup_distribution": dict(setup_counts),
        "sector_distribution": dict(sector_counts),
        "quality_distribution": dict(quality_counts),
        "risk_flag_distribution": dict(risk_counts),
        "top_candidates": top_candidates,
        "market_context": market_data,
        "freshness": {"watchlist_date": target_date},
        "lineage": {
            "watchlist": f"daily_watchlist:{target_date}",
            "market_context": market_data.get("lineage", {})
            if isinstance(market_data, dict)
            else {},
        },
        "artifact_refs": artifact_refs.build(),
        "missing_data": [],
        "caveats": caveats,
        "policy": {"mode": "research_only", "disclaimer": _RESEARCH_ONLY_CAVEAT},
    }
    return ToolOutput(
        data=data,
        summary=f"Deep summary of {len(rows)} persisted watchlist candidates on {target_date}.",
        warnings=caveats,
    )


def generate_shortlist(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
    top: int | None = None,
    min_score: float | None = None,
) -> ToolOutput:
    """Create a deterministic research shortlist from persisted watchlist data."""
    target_date = _resolve_watchlist_date(conn, date)
    limit = _normalize_positive_int(top, default=5, maximum=20)
    threshold = float(min_score) if min_score is not None else 0.0
    if target_date is None:
        caveat = "No persisted daily watchlist is available for shortlist generation."
        return ToolOutput(
            data=_missing_payload(
                "shortlist.generate", None, date, ["daily_watchlist"], caveat
            ),
            summary=caveat,
            warnings=[caveat],
        )

    watchlist_rows = get_watchlist_rich(conn, target_date)
    rows = [row for row in watchlist_rows if float(row.get("score") or 0) >= threshold]
    sectors = _symbol_sector_map(conn, [row["symbol"] for row in rows])
    sector_scores = _sector_score_map(conn, target_date)
    ranked: list[dict[str, Any]] = []
    for row in rows:
        evidence = (
            row.get("evidence_json")
            if isinstance(row.get("evidence_json"), dict)
            else {}
        )
        risks = _risk_flags(row.get("risk_flags_json"))
        sector = sectors.get(row["symbol"])
        sector_score = float(sector_scores.get(sector, 0.0))
        candidate_score = float(row.get("score") or 0.0)
        risk_quality = float(evidence.get("risk_quality_score") or 0.0)
        penalty = min(0.20, 0.04 * len(risks))
        shortlist_score = round(
            max(
                0.0,
                0.75 * candidate_score
                + 0.15 * sector_score
                + 0.10 * risk_quality
                - penalty,
            ),
            6,
        )
        reasons = [
            f"persisted candidate score={candidate_score:.3f}",
            f"setup={row.get('setup_type') or 'UNCLASSIFIED'}",
            f"risk quality={risk_quality:.3f}",
        ]
        if sector:
            reasons.append(f"sector={sector} sector_score={sector_score:.3f}")
        ranked.append(
            {
                "symbol": row["symbol"],
                "shortlist_score": shortlist_score,
                "candidate_score": candidate_score,
                "candidate_class": row.get("candidate_class"),
                "setup_type": row.get("setup_type"),
                "sector": sector,
                "sector_score": sector_score,
                "risk_quality_score": risk_quality,
                "risk_flags": risks,
                "data_quality_status": row.get("data_quality_status"),
                "why_shortlisted": reasons,
                "why_not_immediate": (
                    [f"risk flag: {flag}" for flag in risks]
                    or [
                        "No execution conclusion is produced; confirmation remains required."
                    ]
                ),
            }
        )
    ranked.sort(key=lambda item: (-item["shortlist_score"], item["symbol"]))
    selected = ranked[:limit]
    caveats = [_RESEARCH_ONLY_CAVEAT]
    missing_data: list[str] = []
    if len(rows) < limit:
        caveats.append(
            f"Only {len(rows)} candidates met the persisted score threshold {threshold:.3f}."
        )
    if not watchlist_rows:
        missing_data.append("daily_watchlist")
    if not rows:
        missing_data.append("eligible_watchlist_candidates")
    if not sector_scores:
        missing_data.append("sector_strength_snapshot")
        caveats.append(
            "Sector component defaulted to 0.0 because no persisted sector "
            "strength snapshot was available."
        )
    artifact_refs = ArtifactReferenceBuilder()
    artifact_refs.add_if_present("daily_watchlist", target_date, bool(watchlist_rows))
    artifact_refs.add_if_present(
        "sector_strength_snapshot", target_date, bool(sector_scores)
    )
    lineage_sources: list[str] = []
    if watchlist_rows:
        lineage_sources.append("persisted watchlist")
    if sector_scores:
        lineage_sources.append("persisted sector snapshots")
    data = {
        "tool": "shortlist.generate",
        "available": bool(selected),
        "requested_date": date,
        "as_of_date": target_date,
        "methodology": {
            "version": "shortlist-v1",
            "formula": "0.75*candidate_score + 0.15*sector_score + 0.10*risk_quality - risk_flag_penalty",
            "top": limit,
            "min_score": threshold,
        },
        "shortlist": selected,
        "considered_count": len(rows),
        "artifact_refs": artifact_refs.build(),
        "freshness": {
            "watchlist_date": target_date if watchlist_rows else None,
            "sector_context_date": target_date if sector_scores else None,
        },
        "lineage": {
            "source": " and ".join(lineage_sources)
            or "no persisted shortlist artifacts"
        },
        "missing_data": missing_data,
        "caveats": caveats,
        "policy": {"mode": "research_only", "disclaimer": _RESEARCH_ONLY_CAVEAT},
    }
    return ToolOutput(
        data=data,
        summary=f"Generated a deterministic research shortlist of {len(selected)} symbol(s) for {target_date}.",
        warnings=caveats,
    )


def generate_research_scenario(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
    *,
    market_regime_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
    sector_strength_requirement: ContextRequirement = ContextRequirement.NOT_REQUESTED,
) -> ToolOutput:
    """Build a conditional, research-only scenario from deep-symbol artifacts."""
    analysis_output = deep_symbol_analysis(
        conn,
        symbol=symbol,
        date=date,
        market_regime_requirement=market_regime_requirement,
        sector_strength_requirement=sector_strength_requirement,
    )
    analysis = _tool_data(analysis_output)
    normalized_symbol = _require_symbol(symbol)
    target_date = analysis.get("as_of_date") if isinstance(analysis, dict) else date
    if not isinstance(analysis, dict) or not analysis.get("available"):
        caveat = (
            f"Insufficient persisted data to build a scenario for {normalized_symbol}."
        )
        return ToolOutput(
            data=_missing_payload(
                "scenario.generate_research_plan",
                normalized_symbol,
                target_date,
                ["deep_symbol_analysis"],
                caveat,
            ),
            summary=caveat,
            warnings=list(dict.fromkeys([caveat, *_tool_warnings(analysis_output)])),
        )

    candidate = analysis.get("candidate") or {}
    feature = analysis.get("feature_context") or {}
    levels = analysis.get("levels") or {}
    setup_type = str(candidate.get("setup_type") or "UNCLASSIFIED")
    evidence_output = get_setup_history(conn, setup_type=setup_type, date=target_date)
    evidence_data = _tool_data(evidence_output)
    as_of_date = calendar_date.fromisoformat(str(target_date))
    build = ScenarioPlanBuilder().build(
        symbol=normalized_symbol,
        as_of_date=as_of_date,
        candidate=candidate,
        feature=feature,
        levels=levels,
        quality=analysis.get("quality") or {},
        artifact_refs=analysis.get("artifact_refs") or [],
        freshness=analysis.get("freshness") or {},
        analysis_caveats=[*_tool_warnings(analysis_output), _RESEARCH_ONLY_CAVEAT],
        missing_data=analysis.get("missing_data") or [],
        setup_evidence=evidence_data,
        setup_evidence_caveats=_tool_warnings(evidence_output),
    )
    validate_research_scenario_payload(build.payload)
    repository = ResearchModelsRepository(conn)
    repository.create_symbol_level_snapshot(build.level_snapshot)
    repository.create_setup_evidence_snapshot(build.setup_evidence_snapshot)
    repository.create_research_scenario_plan(build.scenario_plan)
    data = build.payload
    caveats = list(data["caveats"])
    return ToolOutput(
        data=data,
        summary=f"Generated a conditional research scenario for {normalized_symbol} as of {target_date}.",
        warnings=caveats,
    )


def get_setup_history(
    conn: duckdb.DuckDBPyConnection,
    setup_type: str,
    horizon_sessions: int | None = None,
    date: str | None = None,
) -> ToolOutput:
    """Return persisted outcome evidence for one setup type."""
    normalized_setup = str(setup_type or "").strip().upper()
    if not normalized_setup:
        raise ToolExecutionError("evidence.get_setup_history requires 'setup_type'.")
    horizon = _normalize_positive_int(horizon_sessions, default=20, maximum=252)
    target_date = _normalize_optional_date(date)
    where = ["setup_type = ?", "horizon_sessions = ?"]
    params: list[Any] = [normalized_setup, horizon]
    if target_date is not None:
        where.append("as_of_date <= ?")
        params.append(target_date)
    row = conn.execute(
        f"""
        SELECT as_of_date::VARCHAR, horizon_sessions, setup_type, candidate_count,
               avg_forward_return, median_forward_return, avg_excess_return,
               hit_rate, failure_rate, avg_max_drawdown, computed_at::VARCHAR,
               evaluation_run_id, evaluator_version, metric_policy_version
        FROM setup_type_performance
        WHERE {" AND ".join(where)}
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is None:
        caveat = (
            f"No persisted outcome evidence exists for {normalized_setup} at "
            f"{horizon} sessions."
        )
        return ToolOutput(
            data=_missing_payload(
                "evidence.get_setup_history",
                None,
                target_date,
                ["setup_type_performance"],
                caveat,
            ),
            summary=caveat,
            warnings=[caveat],
        )
    columns = [
        "as_of_date",
        "horizon_sessions",
        "setup_type",
        "candidate_count",
        "avg_forward_return",
        "median_forward_return",
        "avg_excess_return",
        "hit_rate",
        "failure_rate",
        "avg_max_drawdown",
        "computed_at",
        "evaluation_run_id",
        "evaluator_version",
        "metric_policy_version",
    ]
    evidence = dict(zip(columns, row, strict=True))
    sample_size = int(evidence.get("candidate_count") or 0)
    caveats = [_RESEARCH_ONLY_CAVEAT]
    if sample_size < 20:
        caveats.append(f"Small sample size: {sample_size} candidate outcome(s).")
    artifact_refs = ArtifactReferenceBuilder()
    artifact_refs.add_if_present(
        "setup_type_performance",
        f"{normalized_setup}:{horizon}:{evidence['as_of_date']}",
        True,
    )
    data = {
        "tool": "evidence.get_setup_history",
        "available": True,
        "requested_date": date,
        "as_of_date": evidence["as_of_date"],
        "setup_type": normalized_setup,
        "horizon_sessions": horizon,
        "evidence": evidence,
        "artifact_refs": artifact_refs.build(),
        "freshness": {"computed_at": evidence.get("computed_at")},
        "lineage": {
            "evaluation_run_id": evidence.get("evaluation_run_id"),
            "evaluator_version": evidence.get("evaluator_version"),
            "metric_policy_version": evidence.get("metric_policy_version"),
        },
        "missing_data": [],
        "caveats": caveats,
        "policy": {"mode": "research_only", "disclaimer": _RESEARCH_ONLY_CAVEAT},
    }
    return ToolOutput(
        data=data,
        summary=(
            f"Persisted setup evidence for {normalized_setup}, {horizon} sessions, "
            f"sample={sample_size}."
        ),
        warnings=caveats,
    )


def _resolve_symbol_date(
    conn: duckdb.DuckDBPyConnection, symbol: str, value: str | None
) -> str | None:
    normalized = _normalize_optional_date(value)
    if normalized is not None:
        return normalized
    row = conn.execute(
        """
        SELECT MAX(candidate_date) FROM (
            SELECT MAX(date)::DATE AS candidate_date FROM candidate_score WHERE symbol = ?
            UNION ALL
            SELECT MAX(date)::DATE AS candidate_date FROM feature_snapshot WHERE symbol = ?
            UNION ALL
            SELECT MAX(CAST(time AS DATE)) AS candidate_date
            FROM canonical_ohlcv WHERE symbol = ? AND interval = '1D'
        )
        """,
        [symbol, symbol, symbol],
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _resolve_watchlist_date(
    conn: duckdb.DuckDBPyConnection, value: str | None
) -> str | None:
    normalized = _normalize_optional_date(value)
    if normalized is not None:
        return normalized
    row = conn.execute("SELECT MAX(date)::VARCHAR FROM daily_watchlist").fetchone()
    return row[0] if row and row[0] else None


def _normalize_optional_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_date(value)
    except CommandValidationError as exc:
        raise ToolExecutionError(str(exc)) from exc


def _require_symbol(value: str) -> str:
    symbol = normalize_symbol(value)
    if not symbol:
        raise ToolExecutionError("A nonblank symbol is required.")
    return symbol


def _normalize_positive_int(
    value: int | str | None, *, default: int, maximum: int
) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ToolExecutionError("Expected a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolExecutionError("Expected a positive integer.") from exc
    if parsed <= 0 or parsed > maximum:
        raise ToolExecutionError(f"Value must be between 1 and {maximum}.")
    return parsed


def _feature_snapshot(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT close, ma20, ma50, ma100, ma20_slope, ma50_slope,
               volume_ma20, volume_ratio, atr14, return_20d, return_60d,
               COALESCE((SELECT relative_return FROM relative_strength_snapshot rs
                         WHERE rs.symbol = feature_snapshot.symbol
                           AND rs.date = feature_snapshot.date
                           AND rs.horizon_sessions = 20
                           AND rs.data_status = 'SUCCESS'
                           AND rs.benchmark_symbol = json_extract_string(feature_snapshot.lineage_json, '$.benchmark_symbol')),
                        rs_20d_vs_vnindex) AS rs_20d_vs_vnindex,
               COALESCE((SELECT relative_return FROM relative_strength_snapshot rs
                         WHERE rs.symbol = feature_snapshot.symbol
                           AND rs.date = feature_snapshot.date
                           AND rs.horizon_sessions = 60
                           AND rs.data_status = 'SUCCESS'
                           AND rs.benchmark_symbol = json_extract_string(feature_snapshot.lineage_json, '$.benchmark_symbol')),
                        rs_60d_vs_vnindex) AS rs_60d_vs_vnindex,
               distance_to_ma20,
               distance_to_52w_high, base_range_30d, close_strength,
               volatility_20d, as_of_bar_date::VARCHAR,
               benchmark_as_of_bar_date::VARCHAR, source_row_count,
               benchmark_row_count, feature_data_status, feature_build_version,
               feature_generated_at::VARCHAR, lineage_json
        FROM feature_snapshot WHERE symbol = ? AND date = ?
        """,
        [symbol, date],
    ).fetchone()
    if row is None:
        return None
    columns = [
        "close",
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
        "volume_ma20",
        "volume_ratio",
        "atr14",
        "return_20d",
        "return_60d",
        "rs_20d_vs_vnindex",
        "rs_60d_vs_vnindex",
        "distance_to_ma20",
        "distance_to_52w_high",
        "base_range_30d",
        "close_strength",
        "volatility_20d",
        "as_of_bar_date",
        "benchmark_as_of_bar_date",
        "source_row_count",
        "benchmark_row_count",
        "feature_data_status",
        "feature_build_version",
        "feature_generated_at",
        "lineage_json",
    ]
    result = dict(zip(columns, row, strict=True))
    result["lineage"] = _json_object(result.pop("lineage_json", None))
    return result


def _recent_bars(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str, *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT CAST(time AS DATE)::VARCHAR, open, high, low, close, volume,
               selected_provider, quality_status, ingestion_run_id
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?
        ORDER BY time DESC LIMIT ?
        """,
        [symbol, date, limit],
    ).fetchall()
    columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "provider",
        "quality_status",
        "ingestion_run_id",
    ]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _level_context(
    bars: list[dict[str, Any]], feature: dict[str, Any] | None
) -> dict[str, Any]:
    if not bars:
        return {
            "latest_close": (feature or {}).get("close"),
            "support_20d": None,
            "resistance_20d": None,
            "low_60d": None,
            "high_60d": None,
            "atr14": (feature or {}).get("atr14"),
        }
    last20 = bars[:20]
    lows20 = [float(row["low"]) for row in last20 if _is_number(row.get("low"))]
    highs20 = [float(row["high"]) for row in last20 if _is_number(row.get("high"))]
    lows60 = [float(row["low"]) for row in bars if _is_number(row.get("low"))]
    highs60 = [float(row["high"]) for row in bars if _is_number(row.get("high"))]
    return {
        "latest_close": bars[0].get("close"),
        "support_20d": min(lows20) if lows20 else None,
        "resistance_20d": max(highs20) if highs20 else None,
        "low_60d": min(lows60) if lows60 else None,
        "high_60d": max(highs60) if highs60 else None,
        "atr14": (feature or {}).get("atr14"),
        "methodology": "bounded extrema over persisted daily bars",
    }


def _symbol_metadata(conn: duckdb.DuckDBPyConnection, symbol: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT symbol, exchange, name, sector, industry, is_active FROM symbol_master WHERE symbol = ?",
        [symbol],
    ).fetchone()
    if row is None:
        return {
            "symbol": symbol,
            "exchange": None,
            "name": None,
            "sector": None,
            "industry": None,
        }
    return dict(
        zip(
            ["symbol", "exchange", "name", "sector", "industry", "is_active"],
            row,
            strict=True,
        )
    )


def _latest_quality(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT CAST(time AS DATE)::VARCHAR, quality_status, selected_provider,
               ingestion_run_id
        FROM canonical_ohlcv
        WHERE symbol = ? AND interval = '1D' AND CAST(time AS DATE) <= ?
        ORDER BY time DESC LIMIT 1
        """,
        [symbol, date],
    ).fetchone()
    if row is None:
        return {"status": "INSUFFICIENT_DATA", "as_of_bar_date": None}
    return {
        "as_of_bar_date": row[0],
        "status": row[1],
        "provider": row[2],
        "ingestion_run_id": row[3],
    }


def _symbol_sector_map(
    conn: duckdb.DuckDBPyConnection, symbols: list[str]
) -> dict[str, str | None]:
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"SELECT symbol, sector FROM symbol_master WHERE symbol IN ({placeholders})",
        symbols,
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _sector_score_map(
    conn: duckdb.DuckDBPyConnection, date: str
) -> dict[str | None, float]:
    output = get_sector_strength(conn, date=date)
    data = _tool_data(output)
    snapshots = data.get("snapshots", []) if isinstance(data, dict) else []
    return {
        item.get("sector"): float(item.get("score") or 0.0)
        for item in snapshots
        if isinstance(item, dict)
    }


def _tool_data(output: ToolOutput) -> dict[str, Any]:
    return output.data if isinstance(output.data, dict) else {}


def _tool_warnings(output: ToolOutput) -> list[str]:
    return [str(item) for item in output.warnings]


def _risk_flags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value else []
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
    return []


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _condition(name: str, left: Any, right: Any, *, operator: str) -> str | None:
    if not _is_number(right):
        return None
    left_text = f"{float(left):.4f}" if _is_number(left) else "latest close"
    return f"{name}: {left_text} {operator} {float(right):.4f}"


def _missing_payload(
    tool: str,
    symbol: str | None,
    requested_date: str | None,
    missing_data: list[str],
    caveat: str,
) -> dict[str, Any]:
    return {
        "tool": tool,
        "available": False,
        "symbol": symbol,
        "requested_date": requested_date,
        "as_of_date": None,
        "artifact_refs": [],
        "freshness": {},
        "lineage": {},
        "missing_data": missing_data,
        "caveats": [caveat],
        "policy": {"mode": "research_only", "disclaimer": _RESEARCH_ONLY_CAVEAT},
    }
