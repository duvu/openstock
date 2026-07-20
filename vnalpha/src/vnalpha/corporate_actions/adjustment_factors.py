"""Deterministic backward-price adjustment factors from corporate actions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

ADJUSTMENT_FACTOR_VERSION = "adjustment-price-multiplier-v2"


class AdjustmentType(str, Enum):
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    BONUS_SHARES = "BONUS_SHARES"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    CASH_DIVIDEND = "CASH_DIVIDEND"


_SHARE_COUNT_ACTIONS = {
    AdjustmentType.SPLIT,
    AdjustmentType.REVERSE_SPLIT,
    AdjustmentType.STOCK_DIVIDEND,
    AdjustmentType.BONUS_SHARES,
    AdjustmentType.RIGHTS_ISSUE,
}


@dataclass(frozen=True, slots=True)
class AdjustmentFactor:
    """Backward-adjustment multipliers for bars before ``action_date``.

    ``price_multiplier`` is always multiplied into historical prices. For a
    2-for-1 split it is ``0.5``; historical 100 becomes 50. ``volume_multiplier``
    is the inverse for share-count-changing actions and 1 for cash dividends.
    """

    symbol: str
    action_date: date
    adjustment_type: AdjustmentType
    price_multiplier: Decimal
    volume_multiplier: Decimal
    numerator: int | None = None
    denominator: int | None = None
    version: str = ADJUSTMENT_FACTOR_VERSION

    @property
    def factor(self) -> Decimal:
        """Backward-compatible alias with unambiguous price semantics."""
        return self.price_multiplier

    def apply_to_price(self, historical_price: Decimal) -> Decimal:
        return historical_price * self.price_multiplier

    def apply_to_volume(self, historical_volume: Decimal) -> Decimal:
        return historical_volume * self.volume_multiplier

    def content_hash(self) -> str:
        payload = {
            **asdict(self),
            "action_date": self.action_date.isoformat(),
            "adjustment_type": self.adjustment_type.value,
            "price_multiplier": str(self.price_multiplier),
            "volume_multiplier": str(self.volume_multiplier),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def calculate_split_factor(old_shares: int, new_shares: int) -> Decimal:
    """Return the backward historical-price multiplier ``old / new``."""
    if old_shares <= 0 or new_shares <= 0:
        raise ValueError("Share counts must be positive")
    return Decimal(old_shares) / Decimal(new_shares)


def calculate_dividend_factor(
    price_before: Decimal,
    dividend_per_share: Decimal,
) -> Decimal:
    if price_before <= 0:
        raise ValueError("Price must be positive")
    if dividend_per_share < 0:
        raise ValueError("Dividend cannot be negative")
    if dividend_per_share >= price_before:
        raise ValueError("Dividend must be smaller than the reference price")
    return (price_before - dividend_per_share) / price_before


def calculate_stock_dividend_factor(
    dividend_shares: int,
    base_shares: int,
) -> Decimal:
    if dividend_shares <= 0 or base_shares <= 0:
        raise ValueError("Share counts must be positive")
    return Decimal(base_shares) / Decimal(base_shares + dividend_shares)


def calculate_rights_issue_factor(
    rights_ratio_new: int,
    rights_ratio_old: int,
    subscription_price: Decimal,
    price_before: Decimal,
) -> Decimal:
    if rights_ratio_old <= 0 or rights_ratio_new <= 0:
        raise ValueError("Rights ratio must be positive")
    if subscription_price <= 0 or price_before <= 0:
        raise ValueError("Prices must be positive")
    total_shares = Decimal(rights_ratio_old + rights_ratio_new)
    total_value = (
        Decimal(rights_ratio_old) * price_before
        + Decimal(rights_ratio_new) * subscription_price
    )
    return (total_value / total_shares) / price_before


def build_adjustment_factor(
    *,
    symbol: str,
    action_date: date,
    adjustment_type: AdjustmentType,
    params: dict[str, object],
) -> AdjustmentFactor:
    """Build one deterministic price/volume multiplier pair."""

    def _dec(key: str) -> Decimal:
        if key not in params:
            raise ValueError(f"Missing required parameter {key!r}")
        return Decimal(str(params[key]))

    def _int(key: str) -> int:
        if key not in params:
            raise ValueError(f"Missing required parameter {key!r}")
        return int(params[key])  # type: ignore[arg-type]

    numerator: int | None = None
    denominator: int | None = None
    if adjustment_type in {AdjustmentType.SPLIT, AdjustmentType.REVERSE_SPLIT}:
        old_shares = _int("old_shares")
        new_shares = _int("new_shares")
        price_multiplier = calculate_split_factor(old_shares, new_shares)
        numerator, denominator = old_shares, new_shares
    elif adjustment_type in {
        AdjustmentType.STOCK_DIVIDEND,
        AdjustmentType.BONUS_SHARES,
    }:
        dividend_shares = _int("dividend_shares")
        base_shares = _int("base_shares")
        price_multiplier = calculate_stock_dividend_factor(dividend_shares, base_shares)
        numerator, denominator = base_shares, base_shares + dividend_shares
    elif adjustment_type is AdjustmentType.CASH_DIVIDEND:
        price_multiplier = calculate_dividend_factor(
            _dec("price_before"), _dec("dividend_per_share")
        )
    elif adjustment_type is AdjustmentType.RIGHTS_ISSUE:
        price_multiplier = calculate_rights_issue_factor(
            _int("rights_ratio_new"),
            _int("rights_ratio_old"),
            _dec("subscription_price"),
            _dec("price_before"),
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported adjustment type {adjustment_type!r}")

    volume_multiplier = (
        Decimal(1) / price_multiplier
        if adjustment_type in _SHARE_COUNT_ACTIONS
        else Decimal(1)
    )
    return AdjustmentFactor(
        symbol=symbol.strip().upper(),
        action_date=action_date,
        adjustment_type=adjustment_type,
        price_multiplier=price_multiplier,
        volume_multiplier=volume_multiplier,
        numerator=numerator,
        denominator=denominator,
    )


__all__ = [
    "ADJUSTMENT_FACTOR_VERSION",
    "AdjustmentFactor",
    "AdjustmentType",
    "build_adjustment_factor",
    "calculate_dividend_factor",
    "calculate_rights_issue_factor",
    "calculate_split_factor",
    "calculate_stock_dividend_factor",
]
