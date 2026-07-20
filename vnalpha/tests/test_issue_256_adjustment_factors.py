"""Tests for issue #256: Adjustment factor calculations."""

from decimal import Decimal

import pytest

from vnalpha.corporate_actions.adjustment_factors import (
    calculate_dividend_factor,
    calculate_rights_issue_factor,
    calculate_split_factor,
    calculate_stock_dividend_factor,
)


def test_two_for_one_split() -> None:
    # Given: 2-for-1 split (1 share becomes 2)
    # When: calculating factor
    factor = calculate_split_factor(old_shares=1, new_shares=2)

    # Then: factor is 2.0 (price halves)
    assert factor == Decimal("2.0")


def test_one_for_two_reverse_split() -> None:
    # Given: 1-for-2 reverse split (2 shares become 1)
    # When: calculating factor
    factor = calculate_split_factor(old_shares=2, new_shares=1)

    # Then: factor is 0.5 (price doubles)
    assert factor == Decimal("0.5")


def test_three_for_two_split() -> None:
    # Given: 3-for-2 split
    # When: calculating factor
    factor = calculate_split_factor(old_shares=2, new_shares=3)

    # Then: factor is 1.5
    assert factor == Decimal("1.5")


def test_split_with_invalid_shares_raises() -> None:
    # When: invalid share counts
    # Then: raises ValueError
    with pytest.raises(ValueError):
        calculate_split_factor(old_shares=0, new_shares=2)
    with pytest.raises(ValueError):
        calculate_split_factor(old_shares=1, new_shares=-1)


def test_cash_dividend_factor() -> None:
    # Given: $2 dividend on $100 stock
    # When: calculating factor
    factor = calculate_dividend_factor(
        price_before=Decimal("100"),
        dividend_per_share=Decimal("2"),
    )

    # Then: factor is 0.98
    assert factor == Decimal("0.98")


def test_large_dividend_factor() -> None:
    # Given: $10 dividend on $100 stock
    # When: calculating factor
    factor = calculate_dividend_factor(
        price_before=Decimal("100"),
        dividend_per_share=Decimal("10"),
    )

    # Then: factor is 0.9
    assert factor == Decimal("0.9")


def test_dividend_with_invalid_inputs_raises() -> None:
    # When: invalid inputs
    # Then: raises ValueError
    with pytest.raises(ValueError):
        calculate_dividend_factor(Decimal("0"), Decimal("2"))
    with pytest.raises(ValueError):
        calculate_dividend_factor(Decimal("100"), Decimal("-1"))


def test_rights_issue_factor() -> None:
    # Given: 1-for-5 rights at $50, stock at $100
    # When: calculating factor
    factor = calculate_rights_issue_factor(
        rights_ratio_new=1,
        rights_ratio_old=5,
        subscription_price=Decimal("50"),
        price_before=Decimal("100"),
    )

    # Then: ex-rights price is (5*100 + 1*50)/6 = 91.67
    # Factor is 91.67/100 = 0.9167
    expected = Decimal("550") / Decimal("600")  # 0.916666...
    assert abs(factor - expected) < Decimal("0.00001")


def test_rights_issue_at_par() -> None:
    # Given: 1-for-1 rights at same price as market
    # When: calculating factor
    factor = calculate_rights_issue_factor(
        rights_ratio_new=1,
        rights_ratio_old=1,
        subscription_price=Decimal("100"),
        price_before=Decimal("100"),
    )

    # Then: no adjustment (factor = 1.0)
    assert factor == Decimal("1.0")


def test_rights_issue_with_invalid_inputs_raises() -> None:
    # When: invalid inputs
    # Then: raises ValueError
    with pytest.raises(ValueError):
        calculate_rights_issue_factor(0, 5, Decimal("50"), Decimal("100"))
    with pytest.raises(ValueError):
        calculate_rights_issue_factor(1, 5, Decimal("0"), Decimal("100"))


def test_adjustment_factor_apply_to_price() -> None:
    # Given: an adjustment factor for 2-for-1 split
    from datetime import date

    from vnalpha.corporate_actions.adjustment_factors import (
        AdjustmentFactor,
        AdjustmentType,
    )

    factor_obj = AdjustmentFactor(
        symbol="TEST",
        action_date=date(2026, 7, 17),
        adjustment_type=AdjustmentType.SPLIT,
        factor=Decimal("2.0"),
        numerator=2,
        denominator=1,
    )

    # When: applying to historical price
    historical = Decimal("100")
    adjusted = factor_obj.apply_to_price(historical)

    # Then: price doubles (becomes $200 in new shares)
    assert adjusted == Decimal("200")


def test_stock_dividend_factor() -> None:
    # Given: a 10% stock dividend (1 new share for every 10 held).
    factor = calculate_stock_dividend_factor(dividend_shares=1, base_shares=10)

    # Then: historical price scales by 10/11.
    assert factor == Decimal(10) / Decimal(11)
    assert (Decimal("110") * factor).quantize(Decimal("0.01")) == Decimal("100.00")


def test_bonus_shares_use_same_dilution_math() -> None:
    # A 1-for-1 bonus issue halves the historical price.
    factor = calculate_stock_dividend_factor(dividend_shares=1, base_shares=1)
    assert factor == Decimal("0.5")


def test_stock_dividend_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        calculate_stock_dividend_factor(dividend_shares=0, base_shares=10)
    with pytest.raises(ValueError):
        calculate_stock_dividend_factor(dividend_shares=1, base_shares=0)


def test_build_adjustment_factor_dispatches_all_six_types() -> None:
    from datetime import date

    from vnalpha.corporate_actions.adjustment_factors import (
        AdjustmentType,
        build_adjustment_factor,
    )

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
        assert result.factor > 0
        assert result.version == "adjustment_v1"


def test_build_adjustment_factor_is_deterministic_and_idempotent() -> None:
    from datetime import date

    from vnalpha.corporate_actions.adjustment_factors import (
        AdjustmentType,
        build_adjustment_factor,
    )

    kwargs = {
        "symbol": "FPT",
        "action_date": date(2026, 7, 17),
        "adjustment_type": AdjustmentType.SPLIT,
        "params": {"old_shares": 2, "new_shares": 3},
    }
    first = build_adjustment_factor(**kwargs)
    second = build_adjustment_factor(**kwargs)
    # Same identity and same factor: repeated derivation never drifts.
    assert first == second
    assert first.factor == Decimal(3) / Decimal(2)


def test_build_adjustment_factor_missing_param_fails_closed() -> None:
    from datetime import date

    from vnalpha.corporate_actions.adjustment_factors import (
        AdjustmentType,
        build_adjustment_factor,
    )

    with pytest.raises(ValueError, match="Missing required parameter"):
        build_adjustment_factor(
            symbol="FPT",
            action_date=date(2026, 7, 17),
            adjustment_type=AdjustmentType.SPLIT,
            params={"old_shares": 1},  # new_shares missing
        )
