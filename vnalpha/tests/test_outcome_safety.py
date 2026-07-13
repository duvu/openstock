"""Safety and product boundary tests for Phase 6 outcome tracking."""

from __future__ import annotations

import inspect
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

    def test_calibration_report_uses_research_language(self):
        import vnalpha.outcomes.calibration as cal_mod

        src = inspect.getsource(cal_mod)
        assert "forward return" in src.lower() or "forward_return" in src.lower()
        assert "buy signal" not in src.lower()

    def test_calibration_interpretation_note_present(self):
        import vnalpha.outcomes.calibration as cal_mod

        src = inspect.getsource(cal_mod)
        assert "research" in src.lower() or "evaluation" in src.lower()

    def test_outcome_status_has_no_action_values(self):
        from vnalpha.outcomes.models import OutcomeStatus

        for status in OutcomeStatus:
            assert "buy" not in status.value.lower()
            assert "sell" not in status.value.lower()
            assert "order" not in status.value.lower()


class TestOutcomeScoringIsolation:
    """Outcome evaluator must not recompute watchlists from scoring code."""

    def test_evaluator_does_not_import_scoring(self):
        import vnalpha.outcomes.evaluator as ev_mod

        src = inspect.getsource(ev_mod)
        # Must not import from scoring module directly
        assert "from vnalpha.scoring" not in src
        assert "import scoring" not in src

    def test_evaluator_does_not_import_features(self):
        import vnalpha.outcomes.evaluator as ev_mod

        src = inspect.getsource(ev_mod)
        assert "from vnalpha.features" not in src
        assert "import features" not in src

    def test_aggregations_does_not_import_scoring(self):
        import vnalpha.outcomes.aggregations as agg_mod

        src = inspect.getsource(agg_mod)
        assert "from vnalpha.scoring" not in src

    def test_outcome_commands_cannot_call_generate_watchlist(self):
        """CLI outcome commands must not call generate_watchlist (would recompute)."""
        cli_path = VNALPHA_SRC / "cli.py"
        cli_src = cli_path.read_text()
        # Find the outcome section only
        outcome_section_start = cli_src.find("outcome_app")
        if outcome_section_start == -1:
            return  # No outcome section found yet — skip
        outcome_section = cli_src[outcome_section_start:]
        assert "generate_watchlist" not in outcome_section


class TestOutcomeForwardReturnNonFabricated:
    """Outcome metrics should return None rather than fabricated values."""

    def test_forward_return_none_when_missing_entry(self):
        from vnalpha.outcomes.metrics import forward_return

        assert forward_return(None, 110.0) is None

    def test_forward_return_none_when_missing_exit(self):
        from vnalpha.outcomes.metrics import forward_return

        assert forward_return(100.0, None) is None

    def test_excess_return_none_when_missing_benchmark(self):
        from vnalpha.outcomes.metrics import excess_return_vs_vnindex

        assert excess_return_vs_vnindex(0.10, None) is None

    def test_max_gain_none_when_empty_window(self):
        from vnalpha.outcomes.metrics import max_gain

        assert max_gain([], 100.0) is None


class TestOutcomeDoesNotMutateScoring:
    """Outcome commands must not change scoring weights or thresholds."""

    def test_no_scoring_config_write_in_outcomes(self):
        src = ""
        for path in OUTCOMES_SRC.rglob("*.py"):
            src += path.read_text()
        assert "scoring.yaml" not in src or "write" not in src.lower()
        # Must not directly modify CANONICAL_CANDIDATE_CLASSES or similar
        assert (
            "CANONICAL_CANDIDATE_CLASSES" not in src
            or "=" not in src.split("CANONICAL_CANDIDATE_CLASSES")[1][:10]
        )
