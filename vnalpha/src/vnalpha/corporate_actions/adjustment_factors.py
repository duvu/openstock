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
