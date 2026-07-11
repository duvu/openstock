"""Deterministic setup-quality decomposition."""

from __future__ import annotations


class SetupQualityEvaluator:
    """Score the declared setup dimensions from persisted features and score inputs."""

    def evaluate(
        self, features: dict, score: dict | None, level_count: int
    ) -> dict[str, float]:
        trend = score.get("trend_score") if score else None
        relative_strength = score.get("relative_strength_score") if score else None
        volume = score.get("volume_score") if score else None
        base = score.get("base_score") if score else None
        risk_quality = score.get("risk_quality_score") if score else None
        return {
            "trend_alignment": self._bounded(trend, features.get("ma20_slope")),
            "base_quality": self._bounded(
                base, features.get("base_range_30d"), inverse=True
            ),
            "relative_strength_quality": self._bounded(
                relative_strength, features.get("rs_20d_vs_vnindex")
            ),
            "volume_quality": self._bounded(volume, features.get("volume_ratio")),
            "level_quality": 1.0 if level_count >= 2 else 0.0,
            "risk_penalty": 1.0 - self._bounded(risk_quality),
        }

    @staticmethod
    def _bounded(
        primary: object, fallback: object = None, inverse: bool = False
    ) -> float:
        value = primary if isinstance(primary, (int, float)) else fallback
        if not isinstance(value, (int, float)):
            return 0.0
        if inverse:
            value = 1.0 - min(max(float(value), 0.0), 1.0)
        return min(max(float(value), 0.0), 1.0)
