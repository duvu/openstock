from __future__ import annotations

from types import MappingProxyType

from vnalpha.features.completeness import (
    CompletenessStatus,
    FeatureCompletenessInput,
    FeatureCompletenessProfile,
    evaluate_feature_completeness,
)

_NEUTRAL_FIELDS = {
    "close",
    "ma20",
    "ma50",
    "ma100",
    "ma20_slope",
    "ma50_slope",
    "volume_ma20",
    "volume_ratio",
    "atr14",
    "return_20d",
    "return_60d",
    "distance_to_ma20",
    "distance_to_52w_high",
    "base_range_30d",
    "close_strength",
    "volatility_20d",
}


def _input(
    bar_count: int,
    *,
    exact_date: bool = True,
    missing_neutral: frozenset[str] = frozenset(),
    missing_relative_strength: frozenset[str] = frozenset(),
) -> FeatureCompletenessInput:
    values = {
        name: (None if name in missing_neutral else 1.0) for name in _NEUTRAL_FIELDS
    }
    values.update(
        {
            "rs_20d": None if "rs_20d" in missing_relative_strength else 1.0,
            "rs_60d": None if "rs_60d" in missing_relative_strength else 1.0,
        }
    )
    return FeatureCompletenessInput(
        observed_bar_count=bar_count,
        exact_date=exact_date,
        values=MappingProxyType(values),
    )


def test_standard_profile_reports_missing_required_neutral_feature() -> None:
    # Given: enough history for STANDARD_120 but no MA100 value.
    feature_input = _input(120, missing_neutral=frozenset({"ma100"}))

    # When: the completeness policy evaluates the snapshot.
    result = evaluate_feature_completeness(feature_input)

    # Then: neutral evidence is incomplete with a typed field-level reason.
    assert result.profile is FeatureCompletenessProfile.STANDARD_120
    assert result.neutral_status is CompletenessStatus.INCOMPLETE
    assert result.missing_neutral_fields == ("ma100",)
