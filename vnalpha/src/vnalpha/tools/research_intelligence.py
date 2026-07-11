from __future__ import annotations

import json
from collections import Counter
from typing import Any

import duckdb

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.normalizers import normalize_date, normalize_setup_type, normalize_symbol
from vnalpha.policy.research_language import assert_research_language
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.lineage import get_symbol_lineage
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.quality import get_quality_status
from vnalpha.tools.research_context import get_market_regime, get_symbol_alignment
from vnalpha.warehouse.repositories import get_candidate_score

_RESEARCH_TOOL_VERSION = "assistant-research-intelligence-v1"


def deep_symbol_analysis(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
) -> ToolOutput:
    """Compose a bounded, warehouse-grounded symbol research payload."""

    normalized_symbol = _required_symbol(symbol)
    as_of_date = _resolve_symbol_date(conn, normalized_symbol, date)
    score = get_candidate_score(conn, normalized_symbol, as_of_date)
    feature = _feature_snapshot(conn, normalized_symbol, as_of_date)
    levels = _derived_levels(conn, normalized_symbol, as_of_date)
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

    caveats = _dedupe(
        [
            *_warnings(market),
            *_warnings(sector),
            *_warnings(quality),
            *_warnings(lineage),
            "Derived levels are descriptive ranges from persisted daily bars, not forecasts.",
            "Confidence reflects data completeness and evidence consistency only.",
        ]
    )
    status = "READY" if score is not None and feature is not None else "PARTIAL"
    if score is None and feature is None and not levels.get("bars_used"):
        status = "UNAVAILABLE"

    score_context = _score_context(score)
    technical_context = _technical_context(feature)
    data = {
        "status": status,
        "symbol": normalized_symbol,
        "requested_date": normalize_date(date),
        "as_of_date": as_of_date,
        "score_context": score_context,
        "technical_context": technical_context,
        "levels": levels,
        "market_context": _tool_data(market),
        "sector_context": _tool_data(sector),
        "quality": {
            "feature_data_status": feature.get("feature_data_status") if feature else None,
            "source_row_count": feature.get("source_row_count") if feature else None,
            "benchmark_row_count": feature.get("benchmark_row_count") if feature else None,
            "tool": _tool_data(quality),
        },
        "freshness": {
            "as_of_bar_date": feature.get("as_of_bar_date") if feature else None,
            "benchmark_as_of_bar_date": feature.get("benchmark_as_of_bar_date")
            if feature
            else None,
            "feature_generated_at": feature.get("feature_generated_at") if feature else None,
        },
        "lineage": {
            "score": score.get("lineage_json") if score else None,
            "feature": feature.get("lineage_json") if feature else None,
            "tool": _tool_data(lineage),
        },
        "artifact_refs": [
            f"candidate_score:{normalized_symbol}:{as_of_date}",
            f"feature_snapshot:{normalized_symbol}:{as_of_date}",
            f"canonical_ohlcv:{normalized_symbol}:<=:{as_of_date}",
        ],
        "methodology_version": _RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": missing_data,
    }
    return ToolOutput(
        data=data,
        summary=f"Structured research context for {normalized_symbol} on {as_of_date} ({status}).",
        warnings=caveats if status != "READY" else _warnings(quality),
    )


def summarize_watchlist_deep(
    conn: duckdb.DuckDBPyConnection,
    date: str | None = None,
) -> ToolOutput:
    """Summarize persisted watchlist structure without free-form inference."""

    as_of_date = _resolve_watchlist_date(conn, date)
    rows = _load_watchlist_rows(conn, as_of_date)
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
                "methodology_version": _RESEARCH_TOOL_VERSION,
                "caveats": [caveat],
                "missing_data": ["daily_watchlist"],
            },
            summary="No persisted watchlist is available for deep synthesis.",
            warnings=[caveat],
        )

    class_distribution = Counter(str(row.get("candidate_class") or "UNCLASSIFIED") for row in rows)
    setup_distribution = Counter(str(row.get("setup_type") or "UNCLASSIFIED") for row in rows)
    sector_clusters = Counter(str(row.get("sector") or "UNCLASSIFIED") for row in rows)
    high_rs = sorted(
        (row for row in rows if row.get("rs_20d_vs_vnindex") is not None),
        key=lambda row: float(row["rs_20d_vs_vnindex"]),
        reverse=True,
    )[:10]
    near_confirmation = [
        row
        for row in rows
        if _number(row.get("breakout_score")) >= 0.65
        and -0.08 <= _number(row.get("distance_to_52w_high"), -1.0) <= 0.03
    ][:10]
    extended = [
        row for row in rows if _number(row.get("distance_to_ma20")) > 0.10
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
    missing_data = []
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
        "top_ranked": [_watchlist_identity(row) for row in rows[:10]],
        "research_focus": {
            "high_relative_strength": [_watchlist_identity(row) for row in high_rs],
            "near_confirmation": [_watchlist_identity(row) for row in near_confirmation],
            "extendedness_review": [_watchlist_identity(row) for row in extended],
            "risk_flagged": [_watchlist_identity(row) for row in risk_flagged],
            "low_data_quality": [_watchlist_identity(row) for row in low_quality],
        },
        "quality": "PARTIAL" if missing_data or low_quality else "READY",
        "freshness": {"watchlist_date": as_of_date},
        "artifact_refs": [
            f"daily_watchlist:{as_of_date}",
            f"candidate_score:{as_of_date}",
            f"feature_snapshot:{as_of_date}",
        ],
        "methodology_version": _RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": missing_data,
    }
    return ToolOutput(
        data=data,
        summary=f"Deep watchlist synthesis for {len(rows)} candidates on {as_of_date}.",
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

    as_of_date = _resolve_watchlist_date(conn, date)
    resolved_limit = _bounded_int(limit, name="limit", lower=1, upper=30)
    setup_filter = normalize_setup_type(setup) if setup else None
    sector_filter = sector.strip().casefold() if sector else None
    rows = _load_watchlist_rows(conn, as_of_date)
    if setup_filter:
        rows = [row for row in rows if row.get("setup_type") == setup_filter]
    if sector_filter:
        rows = [
            row
            for row in rows
            if str(row.get("sector") or "").strip().casefold() == sector_filter
        ]

    ranked: list[dict[str, Any]] = []
    for row in rows:
        risk_flags = list(row.get("risk_flags") or [])
        risk_penalty = min(0.20, 0.04 * len(risk_flags))
        extendedness = max(0.0, _number(row.get("distance_to_ma20")) - 0.08)
        extendedness_penalty = min(0.15, extendedness)
        quality_penalty = (
            0.08
            if str(row.get("feature_data_status") or "").upper()
            not in {"", "READY", "COMPLETE"}
            else 0.0
        )
        shortlist_score = _clamp(
            0.65 * _number(row.get("score"))
            + 0.10 * _number(row.get("trend_score"))
            + 0.10 * _number(row.get("relative_strength_score"))
            + 0.15 * _number(row.get("risk_quality_score"))
            - risk_penalty
            - extendedness_penalty
            - quality_penalty
        )
        ranked.append(
            {
                "symbol": row.get("symbol"),
                "watchlist_rank": row.get("rank"),
                "candidate_score": row.get("score"),
                "shortlist_score": round(shortlist_score, 6),
                "candidate_class": row.get("candidate_class"),
                "setup_type": row.get("setup_type"),
                "sector": row.get("sector"),
                "why_shortlisted": _shortlist_reasons(row),
                "risks_to_review": risk_flags
                + (["extendedness requires review"] if extendedness_penalty else [])
                + (["data quality is incomplete"] if quality_penalty else []),
                "confirmation_needed": (
                    "Review current price/volume confirmation and data freshness before forming a conclusion."
                ),
                "artifact_refs": [
                    f"candidate_score:{row.get('symbol')}:{as_of_date}",
                    f"daily_watchlist:{row.get('symbol')}:{as_of_date}",
                ],
            }
        )
    ranked.sort(key=lambda item: (-item["shortlist_score"], item["watchlist_rank"] or 9999))
    candidates = [
        {**item, "research_rank": index}
        for index, item in enumerate(ranked[:resolved_limit], start=1)
    ]
    caveats = [
        "This shortlist prioritizes research review; it is not action guidance.",
        "The formula is deterministic and depends on persisted score, risk, and feature quality.",
        "Human review and fresh data remain required.",
    ]
    missing_data = [] if candidates else ["matching watchlist candidates"]
    data = {
        "status": "READY" if candidates else "UNAVAILABLE",
        "as_of_date": as_of_date,
        "methodology": {
            "version": _RESEARCH_TOOL_VERSION,
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
        summary=f"Generated {len(candidates)} research-priority candidates for {as_of_date}.",
        warnings=caveats if not candidates else [],
    )


def generate_research_scenario(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None = None,
    with_evidence: bool = False,
    with_regime: bool = True,
) -> ToolOutput:
    """Generate a conditional scenario map from persisted symbol context."""

    deep = deep_symbol_analysis(conn, symbol=symbol, date=date)
    context = deep.data if isinstance(deep.data, dict) else {}
    normalized_symbol = _required_symbol(symbol)
    as_of_date = str(context.get("as_of_date") or normalize_date(date))
    levels = context.get("levels") if isinstance(context.get("levels"), dict) else {}
    technical = (
        context.get("technical_context")
        if isinstance(context.get("technical_context"), dict)
        else {}
    )
    close = technical.get("close")
    resistance = levels.get("resistance_20d") or levels.get("resistance_60d")
    support = levels.get("support_20d") or levels.get("support_60d")
    volume_ratio = technical.get("volume_ratio")
    missing_data = list(context.get("missing_data") or [])
    if close is None:
        missing_data.append("current close")
    if support is None or resistance is None:
        missing_data.append("derived support/resistance levels")

    scenarios = {
        "base_case": {
            "condition": _range_condition(close, support, resistance),
            "evidence_to_watch": [
                "trend and relative-strength persistence",
                "volume participation",
                "data freshness",
            ],
            "risk_context": "The setup remains descriptive until a persisted condition changes.",
            "caveat": "No future outcome is implied.",
        },
        "confirmation_case": {
            "condition": _confirmation_condition(resistance, volume_ratio),
            "evidence_to_watch": [
                "a persisted close beyond the derived range",
                "volume context relative to its recent average",
                "market and sector context when available",
            ],
            "risk_context": "Confirmation quality weakens if participation or data quality is incomplete.",
            "caveat": "This is a monitoring condition, not an instruction.",
        },
        "failed_confirmation_case": {
            "condition": _failure_condition(support, resistance),
            "evidence_to_watch": [
                "loss of the derived range",
                "weaker relative strength",
                "new risk flags",
            ],
            "risk_context": "A failed condition reduces confidence in the current setup description.",
            "caveat": "Re-run analysis with fresh persisted data.",
        },
        "low_quality_drift_case": {
            "condition": "Evidence remains mixed without a clear persisted confirmation condition.",
            "evidence_to_watch": [
                "stale or partial feature data",
                "low participation",
                "conflicting regime or sector context",
            ],
            "risk_context": "Unclear evidence should lower research priority.",
            "caveat": "No conclusion should be forced from incomplete data.",
        },
    }
    evidence = (
        _tool_data(
            get_setup_history(
                conn,
                setup_type=(context.get("score_context") or {}).get("setup_type"),
                symbol=normalized_symbol,
                date=as_of_date,
                horizon=20,
            )
        )
        if with_evidence
        else None
    )
    caveats = _dedupe(
        [
            *(context.get("caveats") or []),
            "Conditional research scenario only; future confirmation is required.",
            "The scenario map is not an execution instruction.",
        ]
    )
    data = {
        "status": "READY" if not missing_data else "PARTIAL",
        "symbol": normalized_symbol,
        "as_of_date": as_of_date,
        "current_context": {
            "close": close,
            "setup_type": (context.get("score_context") or {}).get("setup_type"),
            "candidate_class": (context.get("score_context") or {}).get("candidate_class"),
            "levels": levels,
        },
        "scenarios": scenarios,
        "monitoring_checklist": [
            "refresh symbol and benchmark data",
            "review quality and lineage",
            "compare current price/volume evidence with derived levels",
            "review market and sector context",
        ],
        "market_context": context.get("market_context") if with_regime else None,
        "historical_evidence": evidence,
        "policy_status": "PASS",
        "artifact_refs": list(context.get("artifact_refs") or []),
        "freshness": context.get("freshness") or {},
        "methodology_version": _RESEARCH_TOOL_VERSION,
        "caveats": caveats,
        "missing_data": _dedupe(missing_data),
    }
    assert_research_language(json.dumps(data, default=str), require_marker=True)
    return ToolOutput(
        data=data,
        summary=f"Conditional research scenario for {normalized_symbol} on {as_of_date}.",
        warnings=caveats if missing_data else [],
    )


def get_setup_history(
    conn: duckdb.DuckDBPyConnection,
    setup_type: str | None = None,
    symbol: str | None = None,
    date: str | None = None,
    horizon: int = 20,
) -> ToolOutput:
    """Return persisted historical setup evidence from outcome tables."""

    as_of_date = normalize_date(date)
    horizon_sessions = _bounded_int(horizon, name="horizon", lower=1, upper=252)
    normalized_symbol = normalize_symbol(symbol) if symbol else None
    resolved_setup = normalize_setup_type(setup_type) if setup_type else None
    if resolved_setup is None and normalized_symbol:
        score_date = _resolve_symbol_date(conn, normalized_symbol, as_of_date)
        score = get_candidate_score(conn, normalized_symbol, score_date)
        resolved_setup = str(score.get("setup_type")) if score and score.get("setup_type") else None
        as_of_date = score_date
    if not resolved_setup:
        raise ToolExecutionError("evidence.get_setup_history requires a setup_type or a symbol with a persisted score.")

    row = conn.execute(
        """
        SELECT as_of_date, candidate_count, avg_forward_return,
               median_forward_return, avg_excess_return, hit_rate,
               failure_rate, avg_max_drawdown, evaluator_version,
               metric_policy_version
        FROM setup_type_performance
        WHERE setup_type = ? AND horizon_sessions = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [resolved_setup, horizon_sessions, as_of_date],
    ).fetchone()
    source = "setup_type_performance"
    if row is None:
        row = conn.execute(
            """
            SELECT MAX(watchlist_date), COUNT(*), AVG(forward_return),
                   MEDIAN(forward_return), AVG(excess_return_vs_vnindex),
                   AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END),
                   AVG(CASE WHEN failure THEN 1.0 ELSE 0.0 END),
                   AVG(max_drawdown), MAX(evaluator_version), MAX(metric_policy_version)
            FROM candidate_outcome
            WHERE setup_type = ? AND horizon_sessions = ?
              AND watchlist_date <= ? AND outcome_status = 'COMPLETE'
            """,
            [resolved_setup, horizon_sessions, as_of_date],
        ).fetchone()
        source = "candidate_outcome_aggregate"
        if row and not row[1]:
            row = None

    if row is None:
        caveats = [
            "No completed persisted outcome sample is available for this setup and horizon.",
            "Historical observations, when available, are descriptive and not predictive.",
        ]
        return ToolOutput(
            data={
                "status": "UNAVAILABLE",
                "setup_type": resolved_setup,
                "symbol": normalized_symbol,
                "as_of_date": as_of_date,
                "horizon_sessions": horizon_sessions,
                "sample_size": 0,
                "metrics": {},
                "methodology_version": None,
                "artifact_refs": [
                    f"setup_type_performance:{resolved_setup}:{horizon_sessions}"
                ],
                "caveats": caveats,
                "missing_data": ["completed setup outcomes"],
            },
            summary="No historical setup evidence is available.",
            warnings=caveats,
        )

    sample_size = int(row[1] or 0)
    caveats = [
        "Historical observations are descriptive and are not predictions.",
        "Outcome statistics depend on the persisted evaluator and metric policy versions.",
    ]
    if sample_size < 20:
        caveats.append("The persisted sample is small; interpret the aggregate with restraint.")
    data = {
        "status": "READY" if sample_size >= 20 else "PARTIAL",
        "setup_type": resolved_setup,
        "symbol": normalized_symbol,
        "as_of_date": str(row[0]) if row[0] is not None else as_of_date,
        "horizon_sessions": horizon_sessions,
        "sample_size": sample_size,
        "metrics": {
            "mean_forward_return": row[2],
            "median_forward_return": row[3],
            "mean_excess_return": row[4],
            "hit_rate": row[5],
            "failure_rate": row[6],
            "mean_max_drawdown": row[7],
        },
        "methodology_version": {
            "evaluator_version": row[8],
            "metric_policy_version": row[9],
            "assistant_tool_version": _RESEARCH_TOOL_VERSION,
        },
        "source": source,
        "artifact_refs": [f"{source}:{resolved_setup}:{horizon_sessions}"],
        "freshness": {"evidence_as_of_date": str(row[0]) if row[0] is not None else None},
        "caveats": caveats,
        "missing_data": [],
    }
    return ToolOutput(
        data=data,
        summary=f"Historical evidence for {resolved_setup} over {horizon_sessions} sessions.",
        warnings=caveats if sample_size < 20 else [],
    )


def _feature_snapshot(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> dict[str, Any] | None:
    columns = [
        "symbol",
        "date",
        "close",
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
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
    row = conn.execute(
        f"SELECT {', '.join(columns)} FROM feature_snapshot WHERE symbol = ? AND date = ?",
        [symbol, date],
    ).fetchone()
    if row is None:
        return None
    result = dict(zip(columns, row, strict=True))
    for key in ("date", "as_of_bar_date", "benchmark_as_of_bar_date", "feature_generated_at"):
        if result.get(key) is not None:
            result[key] = str(result[key])
    result["lineage_json"] = _load_json(result.get("lineage_json"), {})
    return result


def _derived_levels(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT CAST(time AS DATE), high, low, close
        FROM canonical_ohlcv
        WHERE symbol = ? AND CAST(time AS DATE) <= ? AND interval = '1D'
        ORDER BY time DESC
        LIMIT 60
        """,
        [symbol, date],
    ).fetchall()
    recent20 = rows[:20]
    return {
        "bars_used": len(rows),
        "support_20d": min((row[2] for row in recent20 if row[2] is not None), default=None),
        "resistance_20d": max((row[1] for row in recent20 if row[1] is not None), default=None),
        "support_60d": min((row[2] for row in rows if row[2] is not None), default=None),
        "resistance_60d": max((row[1] for row in rows if row[1] is not None), default=None),
        "latest_close": rows[0][3] if rows else None,
        "source": "canonical_ohlcv daily bars",
    }


def _technical_context(feature: dict[str, Any] | None) -> dict[str, Any]:
    if feature is None:
        return {}
    keys = (
        "close",
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
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
    )
    return {key: feature.get(key) for key in keys}


def _score_context(score: dict[str, Any] | None) -> dict[str, Any]:
    if score is None:
        return {}
    keys = (
        "score",
        "candidate_class",
        "setup_type",
        "trend_score",
        "relative_strength_score",
        "volume_score",
        "base_score",
        "breakout_score",
        "risk_quality_score",
        "risk_flags_json",
    )
    return {key: score.get(key) for key in keys}


def _load_watchlist_rows(
    conn: duckdb.DuckDBPyConnection, date: str
) -> list[dict[str, Any]]:
    columns = [
        "rank",
        "symbol",
        "score",
        "candidate_class",
        "setup_type",
        "risk_flags_json",
        "watchlist_lineage_json",
        "sector",
        "trend_score",
        "relative_strength_score",
        "volume_score",
        "base_score",
        "breakout_score",
        "risk_quality_score",
        "rs_20d_vs_vnindex",
        "distance_to_ma20",
        "distance_to_52w_high",
        "feature_data_status",
    ]
    rows = conn.execute(
        """
        SELECT w.rank, w.symbol, w.score, w.candidate_class, w.setup_type,
               w.risk_flags_json, w.lineage_json, s.sector,
               c.trend_score, c.relative_strength_score, c.volume_score,
               c.base_score, c.breakout_score, c.risk_quality_score,
               f.rs_20d_vs_vnindex, f.distance_to_ma20,
               f.distance_to_52w_high, f.feature_data_status
        FROM daily_watchlist w
        LEFT JOIN symbol_master s ON s.symbol = w.symbol
        LEFT JOIN candidate_score c ON c.symbol = w.symbol AND c.date = w.date
        LEFT JOIN feature_snapshot f ON f.symbol = w.symbol AND f.date = w.date
        WHERE w.date = ?
        ORDER BY w.rank
        """,
        [date],
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(zip(columns, row, strict=True))
        item["risk_flags"] = _load_json(item.pop("risk_flags_json"), [])
        item["watchlist_lineage"] = _load_json(item.pop("watchlist_lineage_json"), {})
        result.append(item)
    return result


def _watchlist_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "symbol": row.get("symbol"),
        "score": row.get("score"),
        "candidate_class": row.get("candidate_class"),
        "setup_type": row.get("setup_type"),
        "sector": row.get("sector"),
        "risk_flags": list(row.get("risk_flags") or []),
    }


def _shortlist_reasons(row: dict[str, Any]) -> list[str]:
    reasons = [
        f"persisted watchlist rank {row.get('rank')}",
        f"candidate score {_number(row.get('score')):.3f}",
    ]
    if row.get("setup_type"):
        reasons.append(f"setup {row['setup_type']}")
    if _number(row.get("relative_strength_score")) >= 0.65:
        reasons.append("relative-strength component is comparatively strong")
    if _number(row.get("trend_score")) >= 0.65:
        reasons.append("trend component is comparatively strong")
    return reasons


def _resolve_symbol_date(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str | None
) -> str:
    requested = normalize_date(date)
    row = conn.execute(
        "SELECT MAX(date) FROM candidate_score WHERE symbol = ? AND date <= ?",
        [symbol, requested],
    ).fetchone()
    if row and row[0] is not None:
        return str(row[0])
    feature_row = conn.execute(
        "SELECT MAX(date) FROM feature_snapshot WHERE symbol = ? AND date <= ?",
        [symbol, requested],
    ).fetchone()
    return str(feature_row[0]) if feature_row and feature_row[0] is not None else requested


def _resolve_watchlist_date(conn: duckdb.DuckDBPyConnection, date: str | None) -> str:
    requested = normalize_date(date)
    row = conn.execute(
        "SELECT MAX(date) FROM daily_watchlist WHERE date <= ?",
        [requested],
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else requested


def _required_symbol(value: str) -> str:
    symbol = normalize_symbol(value or "")
    if not symbol:
        raise ToolExecutionError("A nonblank symbol is required.")
    return symbol


def _bounded_int(value: Any, *, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool):
        raise ToolExecutionError(f"{name} must be an integer between {lower} and {upper}.")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolExecutionError(
            f"{name} must be an integer between {lower} and {upper}."
        ) from exc
    if resolved < lower or resolved > upper:
        raise ToolExecutionError(f"{name} must be between {lower} and {upper}.")
    return resolved


def _range_condition(close: Any, support: Any, resistance: Any) -> str:
    if close is None or support is None or resistance is None:
        return "Persisted range evidence is incomplete; refresh data before evaluating the base case."
    return f"Persisted close {close} remains between derived support {support} and resistance {resistance}."


def _confirmation_condition(resistance: Any, volume_ratio: Any) -> str:
    if resistance is None:
        return "A confirmation condition cannot be derived because resistance evidence is unavailable."
    participation = (
        f" with volume ratio context {volume_ratio}"
        if volume_ratio is not None
        else " with participation evidence still required"
    )
    return f"A future persisted close beyond derived resistance {resistance}{participation}."


def _failure_condition(support: Any, resistance: Any) -> str:
    if support is None and resistance is None:
        return "The current setup loses consistency with newly persisted price/quality evidence."
    return (
        f"A persisted move back below the reviewed range (support {support}, resistance {resistance}) "
        "or a material deterioration in quality evidence."
    )


def _tool_data(output: ToolOutput) -> Any:
    return output.data


def _warnings(output: ToolOutput) -> list[str]:
    return list(output.warnings or [])


def _load_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


__all__ = [
    "deep_symbol_analysis",
    "generate_research_scenario",
    "generate_shortlist",
    "get_setup_history",
    "summarize_watchlist_deep",
]
