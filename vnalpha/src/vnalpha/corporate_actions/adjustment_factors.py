"""Adjustment factor calculation from corporate actions for issue #256."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class AdjustmentType(str, Enum):
    """Type of price adjustment."""

    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    BONUS_SHARES = "BONUS_SHARES"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    CASH_DIVIDEND = "CASH_DIVIDEND"


@dataclass(frozen=True, slots=True)
class AdjustmentFactor:
    """Deterministic adjustment factor for a specific date range."""

    symbol: str
    action_date: date
    adjustment_type: AdjustmentType
    factor: Decimal  # Multiplier for historical prices
    numerator: int | None = None  # For splits: new shares
    denominator: int | None = None  # For splits: old shares
    version: str = "adjustment_v1"

    def apply_to_price(self, historical_price: Decimal) -> Decimal:
        """Apply adjustment factor to a historical price."""
        return historical_price * self.factor


def calculate_split_factor(old_shares: int, new_shares: int) -> Decimal:
    """Calculate adjustment factor for a stock split.

    Args:
        old_shares: Number of old shares
        new_shares: Number of new shares after split

    Returns:
        Adjustment factor (new/old ratio)

    Example:
        2-for-1 split: old_shares=1, new_shares=2 → factor=2.0
        Historical $100 becomes $50 after adjustment
    """
    if old_shares <= 0 or new_shares <= 0:
        raise ValueError("Share counts must be positive")
    return Decimal(new_shares) / Decimal(old_shares)


def calculate_dividend_factor(
    price_before: Decimal,
    dividend_per_share: Decimal,
) -> Decimal:
    """Calculate adjustment factor for cash dividend.

    Args:
        price_before: Stock price before ex-dividend date
        dividend_per_share: Cash dividend per share

    Returns:
        Adjustment factor to apply to historical prices

    Example:
        Price=$100, Dividend=$2 → factor=0.98
        Historical $100 becomes $98 after adjustment
    """
    if price_before <= 0:
        raise ValueError("Price must be positive")
    if dividend_per_share < 0:
        raise ValueError("Dividend cannot be negative")

    return (price_before - dividend_per_share) / price_before


def calculate_stock_dividend_factor(
    dividend_shares: int,
    base_shares: int,
) -> Decimal:
    """Calculate adjustment factor for a stock dividend or bonus-share issue.

    A stock dividend / bonus issue distributes ``dividend_shares`` new shares
    for every ``base_shares`` held, with no cash paid. The historical price is
    scaled down by the dilution ratio.

    Args:
        dividend_shares: New shares distributed per ``base_shares`` held.
        base_shares: Existing shares required to receive the distribution.

    Returns:
        Adjustment factor ``base / (base + dividend)``.

    Example:
        10% stock dividend: dividend_shares=1, base_shares=10 → factor≈0.909
        Historical $110 becomes $100 after adjustment.
    """
    if dividend_shares <= 0 or base_shares <= 0:
        raise ValueError("Share counts must be positive")
    return Decimal(base_shares) / Decimal(base_shares + dividend_shares)


def calculate_rights_issue_factor(
    rights_ratio_new: int,
    rights_ratio_old: int,
    subscription_price: Decimal,
    price_before: Decimal,
) -> Decimal:
    """Calculate adjustment factor for rights issue.

    Args:
        rights_ratio_new: New shares offered
        rights_ratio_old: Existing shares required
        subscription_price: Price to buy new shares
        price_before: Stock price before ex-rights date

    Returns:
        Adjustment factor

    Example:
        1-for-5 rights at $50, price=$100 → factor=~0.91
    """
    if rights_ratio_old <= 0 or rights_ratio_new <= 0:
        raise ValueError("Rights ratio must be positive")
    if subscription_price <= 0 or price_before <= 0:
        raise ValueError("Prices must be positive")

    # Theoretical ex-rights price formula
    total_shares = Decimal(rights_ratio_old + rights_ratio_new)
    total_value = (
        Decimal(rights_ratio_old) * price_before
        + Decimal(rights_ratio_new) * subscription_price
    )
    ex_rights_price = total_value / total_shares

    return ex_rights_price / price_before


def build_adjustment_factor(
    *,
    symbol: str,
    action_date: date,
    adjustment_type: AdjustmentType,
    params: dict[str, object],
) -> AdjustmentFactor:
    """Build a deterministic, versioned adjustment factor for any supported action.

    Dispatches to the type-specific calculator so callers derive factors for all
    six supported action types through one contract. The result is fully
    determined by ``(adjustment_type, params)`` and carries an explicit version,
    so repeated calls with identical inputs produce identical factors.

    Args:
        symbol: The affected symbol.
        action_date: The ex/effective date the factor applies from.
        adjustment_type: One of the supported :class:`AdjustmentType` values.
        params: Numeric parameters required by the specific action type.

    Raises:
        ValueError: If a required parameter is missing or the action type is
            unsupported.
    """

    def _dec(key: str) -> Decimal:
        if key not in params:
            raise ValueError(f"Missing required parameter {key!r}")
        return Decimal(str(params[key]))

    def _int(key: str) -> int:
        if key not in params:
            raise ValueError(f"Missing required parameter {key!r}")
        return int(params[key])  # type: ignore[arg-type]

    if adjustment_type in (AdjustmentType.SPLIT, AdjustmentType.REVERSE_SPLIT):
        old_shares = _int("old_shares")
        new_shares = _int("new_shares")
        factor = calculate_split_factor(old_shares, new_shares)
        numerator, denominator = new_shares, old_shares
    elif adjustment_type in (
        AdjustmentType.STOCK_DIVIDEND,
        AdjustmentType.BONUS_SHARES,
    ):
        dividend_shares = _int("dividend_shares")
        base_shares = _int("base_shares")
        factor = calculate_stock_dividend_factor(dividend_shares, base_shares)
        numerator, denominator = base_shares, base_shares + dividend_shares
    elif adjustment_type is AdjustmentType.CASH_DIVIDEND:
        factor = calculate_dividend_factor(
            _dec("price_before"), _dec("dividend_per_share")
        )
        numerator = denominator = None
    elif adjustment_type is AdjustmentType.RIGHTS_ISSUE:
        factor = calculate_rights_issue_factor(
            _int("rights_ratio_new"),
            _int("rights_ratio_old"),
            _dec("subscription_price"),
            _dec("price_before"),
        )
        numerator = denominator = None
    else:  # pragma: no cover - enum is exhaustive
        raise ValueError(f"Unsupported adjustment type {adjustment_type!r}")

    return AdjustmentFactor(
        symbol=symbol,
        action_date=action_date,
        adjustment_type=adjustment_type,
        factor=factor,
        numerator=numerator,
        denominator=denominator,
    )
