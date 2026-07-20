"""Pure valuation-metric computation (issue #258).

All functions are deterministic and fail closed (return ``None``) on missing,
zero or negative inputs rather than emitting a misleading ratio.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValuationInputs:
    """Explicit inputs for one valuation computation."""

    price: float | None
    eps: float | None
    book_value_per_share: float | None


@dataclass(frozen=True, slots=True)
class ValuationMetrics:
    pe_ratio: float | None
    earnings_yield: float | None
    pb_ratio: float | None
    book_yield: float | None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return None
    return numerator / denominator


def compute_valuation_metrics(inputs: ValuationInputs) -> ValuationMetrics:
    """Compute P/E, earnings yield, P/B and book yield.

    P/E and P/B require positive EPS / book value per share; a non-positive
    denominator yields ``None`` (a loss-making or negative-equity firm has no
    meaningful positive multiple). Yields are the reciprocal ratios.
    """
    return ValuationMetrics(
        pe_ratio=_safe_ratio(inputs.price, inputs.eps),
        earnings_yield=_safe_ratio(inputs.eps, inputs.price),
        pb_ratio=_safe_ratio(inputs.price, inputs.book_value_per_share),
        book_yield=_safe_ratio(inputs.book_value_per_share, inputs.price),
    )


def book_value_per_share(
    total_equity: float | None, shares_outstanding: float | None
) -> float | None:
    """Return book value per share, failing closed on missing/non-positive shares."""
    if total_equity is None or shares_outstanding is None:
        return None
    if shares_outstanding <= 0:
        return None
    return total_equity / shares_outstanding


def percentile_rank(value: float | None, population: list[float]) -> float | None:
    """Return the percentile rank (0-100) of ``value`` within ``population``.

    Uses the fraction of population values strictly less than ``value`` plus
    half the ties (mid-rank), giving a deterministic, reproducible result.
    Returns ``None`` when the value is missing or the population is empty.
    """
    if value is None or not population:
        return None
    less = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return 100.0 * (less + 0.5 * equal) / len(population)


__all__ = [
    "ValuationInputs",
    "ValuationMetrics",
    "book_value_per_share",
    "compute_valuation_metrics",
    "percentile_rank",
]
