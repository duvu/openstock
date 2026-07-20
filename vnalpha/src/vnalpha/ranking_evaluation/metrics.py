"""Deterministic ranking-evaluation metric primitives (issue #261)."""

from __future__ import annotations

from statistics import median


def hit_rate(excess_returns: list[float]) -> float | None:
    if not excess_returns:
        return None
    return sum(1 for r in excess_returns if r > 0) / len(excess_returns)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def spearman_rank_correlation(
    ranks: list[float], outcomes: list[float]
) -> float | None:
    """Spearman correlation between assigned rank order and realized outcome.

    Deterministic; returns ``None`` when fewer than two points or zero variance.
    A negative correlation means a lower (better) rank number aligns with higher
    outcomes, so we correlate ``-rank`` with outcome to make "policy is
    informative" positive.
    """
    n = len(ranks)
    if n < 2 or len(outcomes) != n:
        return None
    # Convert to rank-of-values to be a true Spearman on ties-free small sets.
    xr = _to_ranks([-r for r in ranks])
    yr = _to_ranks(outcomes)
    mx = sum(xr) / n
    my = sum(yr) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xr, yr, strict=True))
    vx = sum((a - mx) ** 2 for a in xr)
    vy = sum((b - my) ** 2 for b in yr)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx**0.5 * vy**0.5)


def _to_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for position, idx in enumerate(order):
        ranks[idx] = float(position)
    return ranks


def sector_concentration(sector_counts: dict[str, int]) -> float | None:
    """Herfindahl-Hirschman concentration of the selected set by sector.

    1.0 = all in one sector; lower = more diversified. ``None`` if empty.
    """
    total = sum(sector_counts.values())
    if total == 0:
        return None
    return sum((c / total) ** 2 for c in sector_counts.values())


def turnover(prev_symbols: set[str], current_symbols: set[str]) -> float | None:
    """Fraction of the current selection that was not in the previous one."""
    if not current_symbols:
        return None
    entered = current_symbols - prev_symbols
    return len(entered) / len(current_symbols)


__all__ = [
    "hit_rate",
    "mean",
    "median_or_none",
    "sector_concentration",
    "spearman_rank_correlation",
    "turnover",
]
