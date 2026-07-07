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
    CLOSE_ONLY_V1,
    OHLC_HIGH_LOW_V1,
    benchmark_return,
    classify_hit_failure,
    excess_return_vs_vnindex,
    forward_return,
    max_drawdown,
    max_drawdown_from_lows,
    max_gain,
    max_gain_from_highs,
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


class TestMetricPolicyConstants:
    def test_close_only_v1_defined(self):
        assert CLOSE_ONLY_V1 == "CLOSE_ONLY_V1"

    def test_ohlc_high_low_v1_defined(self):
        assert OHLC_HIGH_LOW_V1 == "OHLC_HIGH_LOW_V1"

    def test_policies_are_distinct(self):
        assert CLOSE_ONLY_V1 != OHLC_HIGH_LOW_V1


class TestMaxGainFromHighs:
    """OHLC_HIGH_LOW_V1: max_gain uses intrabar highs."""

    def test_higher_than_close_based(self):
        closes = [102.0, 103.0, 104.0]
        highs = [105.0, 106.0, 107.0]  # highs always above close
        entry = 100.0
        gain_close = max_gain(closes, entry)
        gain_high = max_gain_from_highs(highs, entry)
        assert gain_high > gain_close

    def test_calculation(self):
        highs = [110.0, 108.0, 112.0]
        result = max_gain_from_highs(highs, 100.0)
        assert abs(result - 0.12) < 1e-9

    def test_empty_highs(self):
        assert max_gain_from_highs([], 100.0) is None

    def test_none_entry(self):
        assert max_gain_from_highs([110.0], None) is None

    def test_zero_entry(self):
        assert max_gain_from_highs([110.0], 0.0) is None


class TestMaxDrawdownFromLows:
    """OHLC_HIGH_LOW_V1: max_drawdown uses intrabar lows."""

    def test_lower_than_close_based(self):
        closes = [98.0, 97.0, 96.0]
        lows = [95.0, 94.0, 93.0]  # lows always below close
        entry = 100.0
        dd_close = max_drawdown(closes, entry)
        dd_low = max_drawdown_from_lows(lows, entry)
        assert dd_low < dd_close  # more negative

    def test_calculation(self):
        lows = [90.0, 92.0, 88.0]
        result = max_drawdown_from_lows(lows, 100.0)
        assert abs(result - (-0.12)) < 1e-9

    def test_empty_lows(self):
        assert max_drawdown_from_lows([], 100.0) is None

    def test_none_entry(self):
        assert max_drawdown_from_lows([90.0], None) is None

    def test_zero_entry(self):
        assert max_drawdown_from_lows([90.0], 0.0) is None

    def test_no_drawdown(self):
        # All lows above entry
        lows = [105.0, 110.0]
        result = max_drawdown_from_lows(lows, 100.0)
        assert result >= 0.0
