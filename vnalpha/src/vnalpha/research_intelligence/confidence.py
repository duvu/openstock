"""Evidence coverage confidence evaluation."""

from __future__ import annotations


class ConfidenceEvaluator:
    """Estimate confidence from available persisted evidence, not prediction certainty."""

    def evaluate(
        self, features: dict | None, score: dict | None, levels: list[dict]
    ) -> float:
        available = sum(
            value is not None
            for value in (features, score, levels if len(levels) >= 2 else None)
        )
        return available / 3
