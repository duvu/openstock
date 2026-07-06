"""Candidate metric calculations for outcome evaluation."""

from __future__ import annotations

from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Metric policy constants
# ---------------------------------------------------------------------------

CLOSE_ONLY_V1 = "CLOSE_ONLY_V1"
"""Use close prices for all metrics (entry, exit, max_gain, max_drawdown).

This is the original policy — max_gain = max(close/entry - 1) and
max_drawdown = min(close/entry - 1).  Conservative: understates both
gains and losses because intrabar extremes are not captured.
"""

OHLC_HIGH_LOW_V1 = "OHLC_HIGH_LOW_V1"
"""Use high prices for max_gain and low prices for max_drawdown.

Entry and exit prices are still close-based. Only the extremes use H/L.
This better captures intrabar risk for drawdown and opportunity for gain.
"""


# ---------------------------------------------------------------------------
# Core metrics (policy-agnostic)
# ---------------------------------------------------------------------------

def forward_return(
    entry_close: Optional[float],
    exit_close: Optional[float],
) -> Optional[float]:
    """Calculate forward return: exit/entry - 1."""
    if entry_close is None or exit_close is None:
        return None
    if entry_close == 0:
        return None
    return exit_close / entry_close - 1


def benchmark_return(
    benchmark_entry: Optional[float],
    benchmark_exit: Optional[float],
) -> Optional[float]:
    """Calculate benchmark return: exit/entry - 1."""
    return forward_return(benchmark_entry, benchmark_exit)


def excess_return_vs_vnindex(
    fwd_return: Optional[float],
    bench_return: Optional[float],
) -> Optional[float]:
    """Calculate excess return: forward_return - benchmark_return."""
    if fwd_return is None or bench_return is None:
        return None
    return fwd_return - bench_return


# ---------------------------------------------------------------------------
# Policy-aware gain/drawdown metrics
# ---------------------------------------------------------------------------

def max_gain(
    window_closes: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max gain over forward window using close prices only (CLOSE_ONLY_V1).

    Returns max(close/entry - 1).  Understates upside vs. true intrabar highs.
    Use max_gain_from_highs() for OHLC_HIGH_LOW_V1.
    """
    if not window_closes or entry_close is None or entry_close == 0:
        return None
    return max(c / entry_close - 1 for c in window_closes)


def max_gain_from_highs(
    window_highs: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max gain using intrabar high prices (OHLC_HIGH_LOW_V1).

    Returns max(high/entry - 1).  Captures the best reachable price within
    each session, giving a more accurate picture of peak upside.
    """
    if not window_highs or entry_close is None or entry_close == 0:
        return None
    return max(h / entry_close - 1 for h in window_highs)


def max_drawdown(
    window_closes: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max drawdown over forward window using close prices only (CLOSE_ONLY_V1).

    Returns min(close/entry - 1) — a negative value or zero.
    Understates risk vs. true intrabar lows.
    Use max_drawdown_from_lows() for OHLC_HIGH_LOW_V1.
    """
    if not window_closes or entry_close is None or entry_close == 0:
        return None
    return min(c / entry_close - 1 for c in window_closes)


def max_drawdown_from_lows(
    window_lows: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max drawdown using intrabar low prices (OHLC_HIGH_LOW_V1).

    Returns min(low/entry - 1) — always <= close-based drawdown.
    Captures worst intrabar loss for a more conservative risk estimate.
    """
    if not window_lows or entry_close is None or entry_close == 0:
        return None
    return min(lo / entry_close - 1 for lo in window_lows)


def classify_hit_failure(
    fwd_return: Optional[float],
    excess_return: Optional[float],
) -> Tuple[Optional[bool], Optional[bool]]:
    """Return (hit, failure) flags.

    hit     = excess_return > 0
    failure = forward_return < 0 AND excess_return < 0
    Returns (None, None) if required values are missing.
    """
    if excess_return is None:
        hit = None
    else:
        hit = excess_return > 0

    if fwd_return is None or excess_return is None:
        failure = None
    else:
        failure = fwd_return < 0 and excess_return < 0

    return hit, failure
