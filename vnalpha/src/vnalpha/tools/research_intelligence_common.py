from __future__ import annotations

import json
from typing import Any

import duckdb

from vnalpha.commands.normalizers import normalize_date, normalize_symbol
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolOutput
from vnalpha.warehouse.repositories import get_candidate_score

RESEARCH_TOOL_VERSION = "assistant-research-intelligence-v1"


def feature_snapshot(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
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
    for key in (
        "date",
        "as_of_bar_date",
        "benchmark_as_of_bar_date",
        "feature_generated_at",
    ):
        if result.get(key) is not None:
            result[key] = str(result[key])
    result["lineage_json"] = load_json(result.get("lineage_json"), {})
    return result


def derived_levels(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
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
        "support_20d": min(
            (row[2] for row in recent20 if row[2] is not None), default=None
        ),
        "resistance_20d": max(
            (row[1] for row in recent20 if row[1] is not None), default=None
        ),
        "support_60d": min(
            (row[2] for row in rows if row[2] is not None), default=None
        ),
        "resistance_60d": max(
            (row[1] for row in rows if row[1] is not None), default=None
        ),
        "latest_close": rows[0][3] if rows else None,
        "source": "canonical_ohlcv daily bars",
    }


def technical_context(feature: dict[str, Any] | None) -> dict[str, Any]:
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


def score_context(score: dict[str, Any] | None) -> dict[str, Any]:
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
    )
    result = {key: score.get(key) for key in keys}
    result["risk_flags"] = list(score.get("risk_flags_json") or [])
    return result


def load_watchlist_rows(
    conn: duckdb.DuckDBPyConnection,
    date: str,
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
        item["risk_flags"] = load_json(item.pop("risk_flags_json"), [])
        item["watchlist_lineage"] = load_json(
            item.pop("watchlist_lineage_json"), {}
        )
        result.append(item)
    return result


def watchlist_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("rank"),
        "symbol": row.get("symbol"),
        "score": row.get("score"),
        "candidate_class": row.get("candidate_class"),
        "setup_type": row.get("setup_type"),
        "sector": row.get("sector"),
        "risk_flags": list(row.get("risk_flags") or []),
    }


def shortlist_reasons(row: dict[str, Any]) -> list[str]:
    reasons = [
        f"persisted watchlist rank {row.get('rank')}",
        f"candidate score {number(row.get('score')):.3f}",
    ]
    if row.get("setup_type"):
        reasons.append(f"setup {row['setup_type']}")
    if number(row.get("relative_strength_score")) >= 0.65:
        reasons.append("relative-strength component is comparatively strong")
    if number(row.get("trend_score")) >= 0.65:
        reasons.append("trend component is comparatively strong")
    return reasons


def resolve_symbol_date(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str | None,
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
    return (
        str(feature_row[0])
        if feature_row and feature_row[0] is not None
        else requested
    )


def resolve_watchlist_date(
    conn: duckdb.DuckDBPyConnection,
    date: str | None,
) -> str:
    requested = normalize_date(date)
    row = conn.execute(
        "SELECT MAX(date) FROM daily_watchlist WHERE date <= ?",
        [requested],
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else requested


def required_symbol(value: str) -> str:
    symbol = normalize_symbol(value or "")
    if not symbol:
        raise ToolExecutionError("A nonblank symbol is required.")
    return symbol


def bounded_int(value: Any, *, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool):
        raise ToolExecutionError(
            f"{name} must be an integer between {lower} and {upper}."
        )
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolExecutionError(
            f"{name} must be an integer between {lower} and {upper}."
        ) from exc
    if resolved < lower or resolved > upper:
        raise ToolExecutionError(f"{name} must be between {lower} and {upper}.")
    return resolved


def tool_data(output: ToolOutput) -> Any:
    return output.data


def warnings(output: ToolOutput) -> list[str]:
    return list(output.warnings or [])


def load_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def get_score(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
) -> dict[str, Any] | None:
    return get_candidate_score(conn, symbol, date)
