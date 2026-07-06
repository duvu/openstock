"""Tests for Phase 6 outcome horizons and metrics."""

import pytest

from vnalpha.outcomes.horizons import (
    BENCHMARK_SYMBOL,
    DEFAULT_HORIZONS,
    is_complete,
    select_entry_close,
    select_exit_close,
    split_bars,
)
from vnalpha.outcomes.metrics import (
    benchmark_return,
    classify_hit_failure,
    excess_return_vs_vnindex,
    forward_return,
    max_drawdown,
    max_gain,
)

# ---- horizons tests ----

class TestDefaultHorizons:
    def test_default_horizons(self):
        assert DEFAULT_HORIZONS == [5, 10, 20, 60]

    def test_benchmark_symbol(self):
        assert BENCHMARK_SYMBOL == "VNINDEX"


class TestSelectEntryClose:
    def test_exact_date_match(self):
        bars = [{"time": "2026-07-01", "close": 100.0}]
        assert select_entry_close(bars, "2026-07-01") == 100.0

    def test_latest_before_date(self):
        bars = [
            {"time": "2026-06-29", "close": 98.0},
            {"time": "2026-06-30", "close": 99.0},
        ]
        # watchlist_date is 2026-07-01, no bar exists, use latest <= date
        assert select_entry_close(bars, "2026-07-01") == 99.0

    def test_no_bars_before_date(self):
        bars = [{"time": "2026-07-02", "close": 101.0}]
        assert select_entry_close(bars, "2026-07-01") is None

    def test_empty_bars(self):
        assert select_entry_close([], "2026-07-01") is None


class TestSelectExitClose:
    def test_nth_bar(self):
        bars = [{"time": f"2026-07-0{i}", "close": float(100 + i)} for i in range(1, 6)]
        assert select_exit_close(bars, 3) == 103.0
        assert select_exit_close(bars, 5) == 105.0

    def test_insufficient_bars(self):
        bars = [{"time": "2026-07-01", "close": 100.0}]
        assert select_exit_close(bars, 20) is None

    def test_exactly_n_bars(self):
        bars = [{"time": f"2026-07-0{i}", "close": float(100 + i)} for i in range(1, 6)]
        assert select_exit_close(bars, 5) == 105.0


class TestIsComplete:
    def test_complete(self):
        bars = [{"time": "x", "close": 1.0}] * 20
        assert is_complete(bars, 20) is True

    def test_pending(self):
        bars = [{"time": "x", "close": 1.0}] * 15
        assert is_complete(bars, 20) is False

    def test_zero_bars(self):
        assert is_complete([], 5) is False


class TestSplitBars:
    def test_split(self):
        bars = [
            {"time": "2026-07-01", "close": 100.0},
            {"time": "2026-07-02", "close": 101.0},
            {"time": "2026-07-03", "close": 102.0},
        ]
        entry, future = split_bars(bars, "2026-07-01")
        assert len(entry) == 1
        assert len(future) == 2
        assert future[0]["time"] == "2026-07-02"


# ---- metrics tests ----

class TestForwardReturn:
    def test_calculation(self):
        assert forward_return(100.0, 110.0) == pytest.approx(0.10)

    def test_loss(self):
        assert forward_return(100.0, 95.0) == pytest.approx(-0.05)

    def test_none_entry(self):
        assert forward_return(None, 110.0) is None

    def test_none_exit(self):
        assert forward_return(100.0, None) is None

    def test_zero_entry(self):
        assert forward_return(0.0, 110.0) is None


class TestBenchmarkReturn:
    def test_calculation(self):
        assert benchmark_return(1000.0, 1030.0) == pytest.approx(0.03)

    def test_none_inputs(self):
        assert benchmark_return(None, 1030.0) is None


class TestExcessReturn:
    def test_calculation(self):
        result = excess_return_vs_vnindex(0.10, 0.03)
        assert result == pytest.approx(0.07)

    def test_none_benchmark(self):
        assert excess_return_vs_vnindex(0.10, None) is None

    def test_none_forward(self):
        assert excess_return_vs_vnindex(None, 0.03) is None


class TestMaxGain:
    def test_calculation(self):
        window = [102.0, 95.0, 108.0, 104.0]
        result = max_gain(window, 100.0)
        assert result == pytest.approx(0.08)

    def test_empty_window(self):
        assert max_gain([], 100.0) is None

    def test_none_entry(self):
        assert max_gain([102.0], None) is None


class TestMaxDrawdown:
    def test_calculation(self):
        window = [102.0, 95.0, 108.0, 104.0]
        result = max_drawdown(window, 100.0)
        assert result == pytest.approx(-0.05)

    def test_empty_window(self):
        assert max_drawdown([], 100.0) is None

    def test_none_entry(self):
        assert max_drawdown([95.0], None) is None


class TestClassifyHitFailure:
    def test_hit(self):
        hit, failure = classify_hit_failure(0.05, 0.04)
        assert hit is True
        assert failure is False

    def test_failure(self):
        hit, failure = classify_hit_failure(-0.03, -0.02)
        assert hit is False
        assert failure is True

    def test_positive_forward_negative_excess(self):
        # Not a hit (excess < 0), not a failure (forward >= 0)
        hit, failure = classify_hit_failure(0.01, -0.02)
        assert hit is False
        assert failure is False

    def test_none_excess(self):
        hit, failure = classify_hit_failure(0.05, None)
        assert hit is None
        assert failure is None

    def test_none_forward(self):
        hit, failure = classify_hit_failure(None, 0.03)
        assert hit is True  # excess is not None
        assert failure is None  # forward is None
