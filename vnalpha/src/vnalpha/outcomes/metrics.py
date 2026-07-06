"""Candidate metric calculations for outcome evaluation."""

from __future__ import annotations

from typing import List, Optional, Tuple


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


def max_gain(
    window_closes: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max gain over forward window: max(close/entry - 1)."""
    if not window_closes or entry_close is None or entry_close == 0:
        return None
    return max(c / entry_close - 1 for c in window_closes)


def max_drawdown(
    window_closes: List[float],
    entry_close: Optional[float],
) -> Optional[float]:
    """Max drawdown over forward window: min(close/entry - 1).

    Returns a negative value or zero (e.g. -0.05 means 5% drawdown).
    """
    if not window_closes or entry_close is None or entry_close == 0:
        return None
    return min(c / entry_close - 1 for c in window_closes)


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
