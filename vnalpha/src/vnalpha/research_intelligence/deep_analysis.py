"""Warehouse-grounded deep symbol analysis builder and persistence adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TypedDict

import duckdb

from vnalpha.research_intelligence.confidence import ConfidenceEvaluator
from vnalpha.research_intelligence.levels import LevelExtractor
from vnalpha.research_intelligence.setup_quality import SetupQualityEvaluator
from vnalpha.warehouse.repositories import get_candidate_score


class DeepSymbolAnalysis(TypedDict):
    symbol: str
    as_of_date: str
    data_freshness: object
    lineage: dict[str, object]
    trend: dict[str, object]
    momentum: dict[str, object]
    relative_strength: dict[str, object]
    volume: dict[str, object]
    volatility: dict[str, object]
    levels: dict[str, object]
    setup_quality: dict[str, object]
    confidence: dict[str, object]
    scenario: dict[str, object]
    risk_caveats: list[object]
    missing_data: list[str]


class DeepAnalysisBuilder:
    """Build and persist a deterministic research context for one symbol/date."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._levels = LevelExtractor()
        self._quality = SetupQualityEvaluator()
        self._confidence = ConfidenceEvaluator()

    def build(
        self,
        symbol: str,
        date: str,
        with_sector: bool = False,
        with_regime: bool = False,
    ) -> DeepSymbolAnalysis:
        features = self._load_features(symbol, date)
        score = get_candidate_score(self._conn, symbol, date)
        levels = self._levels.extract(self._conn, symbol, date)
        missing_data = self._missing_data(
            features, score, levels, with_sector, with_regime
        )
        context = self._assemble(symbol, date, features, score, levels, missing_data)
        self._persist(context)
        return context

    def _load_features(self, symbol: str, date: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM feature_snapshot WHERE symbol = ? AND date = ?",
            [symbol, date],
        ).fetchone()
        if row is None:
            return None
        columns = [description[0] for description in self._conn.description]
        result = dict(zip(columns, row, strict=True))
        if isinstance(result.get("lineage_json"), str):
            result["lineage_json"] = json.loads(result["lineage_json"])
        return result

    def _missing_data(
        self,
        features: dict | None,
        score: dict | None,
        levels: list[dict],
        with_sector: bool,
        with_regime: bool,
    ) -> list[str]:
        missing: list[str] = []
        if features is None:
            missing.append("feature snapshot is unavailable")
        elif features.get("rs_20d_vs_vnindex") is None:
            missing.append("relative strength benchmark data is unavailable")
        if score is None:
            missing.append("candidate score is unavailable")
        if not levels:
            missing.append("canonical OHLCV is unavailable for level extraction")
        if not with_sector:
            missing.append("sector context was not requested")
        if not with_regime:
            missing.append("market regime context was not requested")
        return missing

    def _assemble(
        self,
        symbol: str,
        date: str,
        features: dict | None,
        score: dict | None,
        levels: list[dict],
        missing_data: list[str],
    ) -> DeepSymbolAnalysis:
        feature_data = features or {}
        setup_quality = self._quality.evaluate(feature_data, score, len(levels))
        close = feature_data.get("close")
        ma20 = feature_data.get("ma20")
        trend = (
            "UPTREND"
            if close is not None and ma20 is not None and close >= ma20
            else "NON_UPTREND"
        )
        return {
            "symbol": symbol,
            "as_of_date": date,
            "data_freshness": feature_data.get("feature_data_status", "UNAVAILABLE"),
            "lineage": feature_data.get("lineage_json")
            or (score or {}).get("lineage_json")
            or {},
            "trend": {
                "state": trend,
                "close": close,
                "ma20": ma20,
                "ma50": feature_data.get("ma50"),
            },
            "momentum": {
                "return_20d": feature_data.get("return_20d"),
                "return_60d": feature_data.get("return_60d"),
            },
            "relative_strength": {
                "rs_20d_vs_vnindex": feature_data.get("rs_20d_vs_vnindex"),
                "rs_60d_vs_vnindex": feature_data.get("rs_60d_vs_vnindex"),
            },
            "volume": {
                "ratio": feature_data.get("volume_ratio"),
                "ma20": feature_data.get("volume_ma20"),
            },
            "volatility": {
                "atr14": feature_data.get("atr14"),
                "volatility_20d": feature_data.get("volatility_20d"),
            },
            "levels": {"levels": levels},
            "setup_quality": setup_quality,
            "confidence": self._confidence.evaluate(features, score, levels),
            "scenario": {
                "monitoring": "Monitor whether observed price and volume behavior remains consistent with the persisted setup context.",
                "conditional_confirmation": "Confirmation requires renewed evidence in subsequent persisted data.",
                "invalidation": "Reassess if price behavior materially diverges from the observed support and trend references.",
                "checklist": [
                    "Review data freshness",
                    "Review lineage",
                    "Review risk flags and missing evidence",
                ],
            },
            "risk_caveats": (score or {}).get("risk_flags_json") or [],
            "missing_data": missing_data,
        }

    def _persist(self, analysis: DeepSymbolAnalysis) -> None:
        generated_at = datetime.now(timezone.utc)
        self._conn.execute(
            """
            INSERT INTO setup_analysis (symbol, date, generated_at, analysis_json, artifact_references_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (symbol, date) DO UPDATE SET
                generated_at = excluded.generated_at,
                analysis_json = excluded.analysis_json,
                artifact_references_json = excluded.artifact_references_json
            """,
            [
                analysis["symbol"],
                analysis["as_of_date"],
                generated_at,
                json.dumps(analysis, default=str),
                json.dumps(
                    {
                        "feature_snapshot": analysis["as_of_date"],
                        "candidate_score": analysis["as_of_date"],
                    }
                ),
            ],
        )
        for level in analysis["levels"]["levels"]:
            self._conn.execute(
                """
                INSERT INTO symbol_level_snapshot (symbol, date, level_type, value, strength, derivation)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (symbol, date, level_type) DO UPDATE SET
                    value = excluded.value, strength = excluded.strength, derivation = excluded.derivation
                """,
                [
                    analysis["symbol"],
                    analysis["as_of_date"],
                    level["type"],
                    level["value"],
                    level["strength"],
                    level["derivation"],
                ],
            )
