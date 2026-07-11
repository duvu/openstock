from __future__ import annotations

import json
from datetime import datetime, timezone
from statistics import median
from typing import Literal, TypedDict

import duckdb

from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import RunContext

Rotation = Literal["improving", "stable", "weakening", "insufficient_data"]
Alignment = Literal["strong", "neutral", "weak", "improving", "weakening"]


class SectorStrength(TypedDict):
    sector: str
    rank: int
    median_return: float
    relative_strength_vs_vnindex: float | None
    breadth: float
    rotation: Rotation
    symbol_returns: dict[str, float]
    as_of_date: str
    methodology: str
    freshness: str
    lineage: dict[str, str]
    quality: str
    caveats: list[str]


class SymbolSectorAlignment(TypedDict):
    symbol: str
    sector: str
    alignment: Alignment
    as_of_date: str
    caveats: list[str]


class SectorStrengthBuilder:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def build(
        self, date: str, *, run_ctx: RunContext | None = None
    ) -> list[SectorStrength]:
        benchmark = self._return_for_symbol("VNINDEX", date)
        grouped: dict[str, dict[str, float]] = {}
        for sector, symbol in self._conn.execute(
            """
            SELECT sector, symbol FROM symbol_master
            WHERE coalesce(sector, '') <> '' AND sector <> 'Index'
            """
        ).fetchall():
            symbol_return = self._return_for_symbol(symbol, date)
            if symbol_return is not None:
                grouped.setdefault(sector, {})[symbol] = symbol_return
        rows = sorted(
            (
                (sector, float(median(symbol_returns.values())), symbol_returns)
                for sector, symbol_returns in grouped.items()
            ),
            key=lambda row: row[1],
            reverse=True,
        )
        result: list[SectorStrength] = []
        for rank, (sector, sector_return, symbol_returns) in enumerate(rows, 1):
            caveats = (
                []
                if benchmark is not None
                else ["VNINDEX benchmark data is unavailable"]
            )
            entry: SectorStrength = {
                "sector": sector,
                "rank": rank,
                "median_return": sector_return,
                "relative_strength_vs_vnindex": None
                if benchmark is None
                else sector_return - benchmark,
                "breadth": sum(value > 0 for value in symbol_returns.values())
                / len(symbol_returns),
                "rotation": _rotation(sector_return),
                "symbol_returns": symbol_returns,
                "as_of_date": date,
                "methodology": "sector_strength_v1: median available symbol returns from canonical OHLCV",
                "freshness": "AS_OF_DATE",
                "lineage": {
                    "benchmark": "VNINDEX",
                    "source": "canonical_ohlcv",
                },
                "quality": "complete" if benchmark is not None else "partial",
                "caveats": caveats,
            }
            result.append(entry)
            self._conn.execute(
                """
                INSERT INTO sector_strength_snapshot (date, sector, rank, analysis_json, generated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (date, sector) DO UPDATE SET
                    rank = excluded.rank, analysis_json = excluded.analysis_json,
                    generated_at = excluded.generated_at
                """,
                [date, sector, rank, json.dumps(entry), datetime.now(timezone.utc)],
            )
        log_audit(
            "SECTOR_STRENGTH_BUILT",
            f"Sector strength built for {date}: {len(result)} sectors",
            run_ctx=run_ctx,
            extra={"date": date, "sector_count": len(result)},
            module=__name__,
            function="SectorStrengthBuilder.build",
        )
        return result

    def symbol_alignment(self, symbol: str, date: str) -> SymbolSectorAlignment:
        row = self._conn.execute(
            "SELECT sector FROM symbol_master WHERE symbol = ?", [symbol]
        ).fetchone()
        if row is None or row[0] is None:
            return {
                "symbol": symbol,
                "sector": "unavailable",
                "alignment": "neutral",
                "as_of_date": date,
                "caveats": ["symbol sector metadata is unavailable"],
            }
        rankings = self.build(date)
        symbol_return = self._return_for_symbol(symbol, date)
        sector_entry = next(
            (entry for entry in rankings if entry["sector"] == row[0]), None
        )
        if symbol_return is None or sector_entry is None:
            return {
                "symbol": symbol,
                "sector": row[0],
                "alignment": "neutral",
                "as_of_date": date,
                "caveats": ["insufficient symbol or sector history"],
            }
        alignment: Alignment = (
            "strong" if symbol_return >= sector_entry["median_return"] else "weak"
        )
        return {
            "symbol": symbol,
            "sector": row[0],
            "alignment": alignment,
            "as_of_date": date,
            "caveats": sector_entry["caveats"],
        }

    def _return_for_symbol(self, symbol: str, date: str) -> float | None:
        rows = self._conn.execute(
            """
            SELECT close FROM canonical_ohlcv
            WHERE symbol = ? AND interval = '1D' AND time::DATE <= ?
            ORDER BY time
            """,
            [symbol, date],
        ).fetchall()
        if len(rows) < 2 or rows[0][0] is None or rows[-1][0] is None:
            return None
        return (rows[-1][0] / rows[0][0]) - 1


def _rotation(sector_return: float) -> Rotation:
    if sector_return > 0:
        return "improving"
    if sector_return < 0:
        return "weakening"
    return "stable"
