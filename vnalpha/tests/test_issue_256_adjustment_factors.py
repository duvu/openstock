"""Tests for issue #256 adjustment factor calculations."""

from datetime import date
from decimal import Decimal

import pytest

from vnalpha.corporate_actions.adjustment_factors import (
    ADJUSTMENT_FACTOR_VERSION,
    AdjustmentFactor,
    AdjustmentType,
    build_adjustment_factor,
    calculate_dividend_factor,
    calculate_rights_issue_factor,
    calculate_split_factor,
    calculate_stock_dividend_factor,
)


def test_two_for_one_split_halves_historical_price() -> None:
    assert calculate_split_factor(old_shares=1, new_shares=2) == Decimal("0.5")


def test_one_for_two_reverse_split_doubles_historical_price() -> None:
    assert calculate_split_factor(old_shares=2, new_shares=1) == Decimal("2")


def test_three_for_two_split_uses_old_over_new() -> None:
    assert calculate_split_factor(old_shares=2, new_shares=3) == (
        Decimal(2) / Decimal(3)
    )


def test_split_with_invalid_shares_raises() -> None:
    with pytest.raises(ValueError):
        calculate_split_factor(old_shares=0, new_shares=2)
    with pytest.raises(ValueError):
        calculate_split_factor(old_shares=1, new_shares=-1)


def test_cash_dividend_factor() -> None:
    factor = calculate_dividend_factor(Decimal("100"), Decimal("2"))
    assert factor == Decimal("0.98")


def test_dividend_with_invalid_inputs_raises() -> None:
    with pytest.raises(ValueError):
        calculate_dividend_factor(Decimal("0"), Decimal("2"))
    with pytest.raises(ValueError):
        calculate_dividend_factor(Decimal("100"), Decimal("-1"))
    with pytest.raises(ValueError):
        calculate_dividend_factor(Decimal("100"), Decimal("100"))


def test_rights_issue_factor() -> None:
    factor = calculate_rights_issue_factor(
        1,
        5,
        Decimal("50"),
        Decimal("100"),
    )
    assert abs(factor - Decimal("550") / Decimal("600")) < Decimal("0.00001")


def test_rights_issue_at_par_requires_no_adjustment() -> None:
    assert calculate_rights_issue_factor(
        1,
        1,
        Decimal("100"),
        Decimal("100"),
    ) == Decimal("1")


def test_rights_issue_with_invalid_inputs_raises() -> None:
    with pytest.raises(ValueError):
        calculate_rights_issue_factor(0, 5, Decimal("50"), Decimal("100"))
    with pytest.raises(ValueError):
        calculate_rights_issue_factor(1, 5, Decimal("0"), Decimal("100"))


def test_adjustment_factor_applies_price_and_volume_multipliers() -> None:
    factor = AdjustmentFactor(
        symbol="TEST",
        action_date=date(2026, 7, 17),
        adjustment_type=AdjustmentType.SPLIT,
        price_multiplier=Decimal("0.5"),
        volume_multiplier=Decimal("2"),
        numerator=1,
        denominator=2,
    )
    assert factor.apply_to_price(Decimal("100")) == Decimal("50.0")
    assert factor.apply_to_volume(Decimal("1000")) == Decimal("2000")


def test_stock_dividend_and_bonus_dilution() -> None:
    factor = calculate_stock_dividend_factor(dividend_shares=1, base_shares=10)
    assert factor == Decimal(10) / Decimal(11)
    assert (Decimal("110") * factor).quantize(Decimal("0.01")) == Decimal("100.00")
    assert calculate_stock_dividend_factor(1, 1) == Decimal("0.5")


def test_stock_dividend_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        calculate_stock_dividend_factor(0, 10)
    with pytest.raises(ValueError):
        calculate_stock_dividend_factor(1, 0)


def test_build_adjustment_factor_dispatches_all_six_types() -> None:
    cases = {
        AdjustmentType.SPLIT: {"old_shares": 1, "new_shares": 2},
        AdjustmentType.REVERSE_SPLIT: {"old_shares": 2, "new_shares": 1},
        AdjustmentType.STOCK_DIVIDEND: {"dividend_shares": 1, "base_shares": 10},
        AdjustmentType.BONUS_SHARES: {"dividend_shares": 1, "base_shares": 1},
        AdjustmentType.CASH_DIVIDEND: {
            "price_before": "100",
            "dividend_per_share": "2",
        },
        AdjustmentType.RIGHTS_ISSUE: {
            "rights_ratio_new": 1,
            "rights_ratio_old": 5,
            "subscription_price": "50",
            "price_before": "100",
        },
    }
    for action_type, params in cases.items():
        result = build_adjustment_factor(
            symbol="FPT",
            action_date=date(2026, 7, 17),
            adjustment_type=action_type,
            params=params,
        )
        assert result.adjustment_type is action_type
        assert result.price_multiplier > 0
        assert result.volume_multiplier > 0
        assert result.version == ADJUSTMENT_FACTOR_VERSION


def test_build_adjustment_factor_is_deterministic() -> None:
    kwargs = {
        "symbol": "FPT",
        "action_date": date(2026, 7, 17),
        "adjustment_type": AdjustmentType.SPLIT,
        "params": {"old_shares": 2, "new_shares": 3},
    }
    first = build_adjustment_factor(**kwargs)
    second = build_adjustment_factor(**kwargs)
    assert first == second
    assert first.factor == Decimal(2) / Decimal(3)
    assert first.content_hash() == second.content_hash()


def test_build_adjustment_factor_missing_param_fails_closed() -> None:
    with pytest.raises(ValueError, match="Missing required parameter"):
        build_adjustment_factor(
            symbol="FPT",
            action_date=date(2026, 7, 17),
            adjustment_type=AdjustmentType.SPLIT,
            params={"old_shares": 1},
        )
