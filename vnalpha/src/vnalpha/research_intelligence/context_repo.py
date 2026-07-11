from __future__ import annotations

import json

import duckdb

from vnalpha.research_intelligence.regime import MarketBreadth, MarketRegime
from vnalpha.research_intelligence.sector import (
    SectorStrength,
    SymbolSectorAlignment,
)


def get_market_regime_snapshot(
    conn: duckdb.DuckDBPyConnection, date: str | None = None
) -> MarketRegime | None:
    sql = "SELECT analysis_json FROM market_regime_snapshot"
    params: list[str] = []
    if date is not None:
        sql += " WHERE date = ?"
        params.append(date)
    sql += " ORDER BY date DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    raw = json.loads(row[0])
    if not isinstance(raw, dict) or not isinstance(raw.get("breadth"), dict):
        return None
    raw_breadth = raw["breadth"]
    breadth: MarketBreadth = {
        "advancing_symbols": int(raw_breadth.get("advancing_symbols", 0)),
        "declining_symbols": int(raw_breadth.get("declining_symbols", 0)),
        "unchanged_symbols": int(raw_breadth.get("unchanged_symbols", 0)),
    }
    return {
        "as_of_date": str(raw.get("as_of_date", "")),
        "state": raw.get("state", "insufficient_data"),
        "trend": str(raw.get("trend", "unavailable")),
        "volatility": str(raw.get("volatility", "unavailable")),
        "breadth": breadth,
        "methodology": str(raw.get("methodology", "")),
        "freshness": str(raw.get("freshness", "")),
        "lineage": raw.get("lineage", {}),
        "quality": str(raw.get("quality", "partial")),
        "caveats": list(raw.get("caveats", [])),
    }


def get_ranked_sector_strength(
    conn: duckdb.DuckDBPyConnection, date: str
) -> list[SectorStrength]:
    rows = conn.execute(
        "SELECT analysis_json FROM sector_strength_snapshot WHERE date = ? ORDER BY rank",
        [date],
    ).fetchall()
    return [_sector_strength_from_json(row[0]) for row in rows]


def get_symbol_sector_alignment(
    conn: duckdb.DuckDBPyConnection, symbol: str, date: str
) -> SymbolSectorAlignment:
    sector_row = conn.execute(
        "SELECT sector FROM symbol_master WHERE symbol = ?", [symbol]
    ).fetchone()
    if sector_row is None or sector_row[0] is None:
        return _neutral_alignment(
            symbol, "unavailable", date, "symbol sector metadata is unavailable"
        )
    sector = str(sector_row[0])
    sector_row = conn.execute(
        "SELECT analysis_json FROM sector_strength_snapshot WHERE date = ? AND sector = ?",
        [date, sector],
    ).fetchone()
    if sector_row is None:
        return _neutral_alignment(
            symbol, sector, date, "insufficient symbol or sector history"
        )
    sector_strength = _sector_strength_from_json(sector_row[0])
    symbol_return = sector_strength["symbol_returns"].get(symbol)
    if symbol_return is None:
        return _neutral_alignment(
            symbol, sector, date, "insufficient symbol or sector history"
        )
    return {
        "symbol": symbol,
        "sector": sector,
        "alignment": "strong"
        if symbol_return >= sector_strength["median_return"]
        else "weak",
        "as_of_date": date,
        "caveats": sector_strength["caveats"],
    }


def _sector_strength_from_json(value: str) -> SectorStrength:
    raw = json.loads(value)
    return {
        "sector": str(raw["sector"]),
        "rank": int(raw["rank"]),
        "median_return": float(raw["median_return"]),
        "relative_strength_vs_vnindex": raw.get("relative_strength_vs_vnindex"),
        "breadth": float(raw["breadth"]),
        "rotation": raw["rotation"],
        "symbol_returns": {
            str(symbol): float(symbol_return)
            for symbol, symbol_return in raw["symbol_returns"].items()
        },
        "as_of_date": str(raw["as_of_date"]),
        "methodology": str(raw["methodology"]),
        "freshness": str(raw["freshness"]),
        "lineage": {str(key): str(value) for key, value in raw["lineage"].items()},
        "quality": str(raw["quality"]),
        "caveats": list(raw["caveats"]),
    }


def _neutral_alignment(
    symbol: str, sector: str, date: str, caveat: str
) -> SymbolSectorAlignment:
    return {
        "symbol": symbol,
        "sector": sector,
        "alignment": "neutral",
        "as_of_date": date,
        "caveats": [caveat],
    }
