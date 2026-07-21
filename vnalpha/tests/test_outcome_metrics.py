"""Tests for Phase 6 outcome horizons and metrics."""

from vnalpha.outcomes.horizons import (
    DEFAULT_HORIZONS,
)

# ---- horizons tests ----


class TestDefaultHorizons:
    def test_default_horizons(self):
        assert DEFAULT_HORIZONS == [5, 10, 20, 60]


# ---- metrics tests ----
