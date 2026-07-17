"""Horizon bar selection for outcome evaluation."""

from __future__ import annotations

from typing import Dict, List, Optional

DEFAULT_HORIZONS: List[int] = [5, 10, 20, 60]

BENCHMARK_SYMBOL = "VNINDEX"


def select_entry_close(
    bars: List[Dict],
    watchlist_date: str,
) -> Optional[float]:
    for bar in bars:
        if bar["time"] > watchlist_date:
            return bar["close"]
    return None


def select_exit_close(
    bars_after_entry: List[Dict],
    n: int,
) -> Optional[float]:
    """Return close at the Nth bar after entry (1-indexed N).

    bars_after_entry: bars strictly AFTER the watchlist_date, sorted ascending.
    n: horizon in sessions (e.g. 20 means the 20th bar).
    Returns None if fewer than n bars are available.
    """
    if len(bars_after_entry) < n:
        return None
    return bars_after_entry[n - 1]["close"]


def get_forward_window(
    bars_after_entry: List[Dict],
    n: int,
) -> List[Dict]:
    """Return the forward window (first n bars after entry)."""
    return bars_after_entry[:n]


def count_bars_available(bars_after_entry: List[Dict]) -> int:
    """Return count of bars available after entry."""
    return len(bars_after_entry)


def is_complete(bars_after_entry: List[Dict], n: int) -> bool:
    """True if at least n bars are available after entry."""
    return len(bars_after_entry) >= n


def split_bars(
    bars: List[Dict],
    watchlist_date: str,
) -> tuple[List[Dict], List[Dict]]:
    """Split bars into at-or-before and strictly-after watchlist_date.

    Returns (entry_bars, future_bars).
    """
    entry_bars = [b for b in bars if b["time"] <= watchlist_date]
    future_bars = [b for b in bars if b["time"] > watchlist_date]
    return entry_bars, future_bars
