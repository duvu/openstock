"""Safety and product boundary tests for Phase 6 outcome tracking."""

from __future__ import annotations

from pathlib import Path

VNALPHA_SRC = Path(__file__).parents[1] / "src" / "vnalpha"
OUTCOMES_SRC = VNALPHA_SRC / "outcomes"
FORBIDDEN_EXECUTION_TERMS = [
    "buy signal",
    "sell signal",
    "place order",
    "execute order",
    "portfolio action",
    "investment advice",
    "order execution",
    "broker execution",
]


class TestOutcomeLanguageBoundary:
    """Outcome modules must not contain execution or advice language."""

    def _get_all_outcome_source(self) -> str:
        """Concatenate all .py source files in outcomes/."""
        src = ""
        for path in OUTCOMES_SRC.rglob("*.py"):
            src += path.read_text()
        return src.lower()

    def test_no_trading_execution_terms(self):
        src = self._get_all_outcome_source()
        for term in FORBIDDEN_EXECUTION_TERMS:
            assert term not in src, f"Forbidden term '{term}' found in outcomes/ source"
