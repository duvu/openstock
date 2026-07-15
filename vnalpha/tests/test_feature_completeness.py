from __future__ import annotations

from datetime import date
from types import MappingProxyType

import duckdb
import pytest

from vnalpha.data_availability.checks import get_feature_snapshot_evidence
from vnalpha.features.completeness import (
    CompletenessStatus,
    FeatureCompletenessInput,
    FeatureCompletenessProfile,
    evaluate_feature_completeness,
)
from vnalpha.features.snapshot_store import save_feature_snapshot
from vnalpha.research_intelligence.breadth import load_breadth_context
from vnalpha.scoring.generate_watchlist import score_universe
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import upsert_symbol

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


@pytest.mark.parametrize(
    ("bar_count", "expected_profile", "expected_status"),
    [
        (19, FeatureCompletenessProfile.MINIMAL_20, CompletenessStatus.INCOMPLETE),
        (20, FeatureCompletenessProfile.MINIMAL_20, CompletenessStatus.COMPLETE),
        (60, FeatureCompletenessProfile.MINIMAL_20, CompletenessStatus.COMPLETE),
        (100, FeatureCompletenessProfile.MINIMAL_20, CompletenessStatus.COMPLETE),
        (120, FeatureCompletenessProfile.STANDARD_120, CompletenessStatus.COMPLETE),
        (252, FeatureCompletenessProfile.FULL_252, CompletenessStatus.COMPLETE),
    ],
)
def test_profile_matches_available_history(
    bar_count: int,
    expected_profile: FeatureCompletenessProfile,
    expected_status: CompletenessStatus,
) -> None:
    # Given: feature values needed by every profile.
    feature_input = _input(bar_count)

    # When: the completeness policy evaluates available history.
    result = evaluate_feature_completeness(feature_input)

    # Then: the strongest eligible profile and neutral outcome are explicit.
    assert result.profile is expected_profile
    assert result.neutral_status is expected_status


def test_standard_profile_reports_missing_required_neutral_feature() -> None:
    # Given: enough history for STANDARD_120 but no MA100 value.
    feature_input = _input(120, missing_neutral=frozenset({"ma100"}))

    # When: the completeness policy evaluates the snapshot.
    result = evaluate_feature_completeness(feature_input)

    # Then: neutral evidence is incomplete with a typed field-level reason.
    assert result.profile is FeatureCompletenessProfile.STANDARD_120
    assert result.neutral_status is CompletenessStatus.INCOMPLETE
    assert result.missing_neutral_fields == ("ma100",)


def test_missing_relative_strength_does_not_invalidate_neutral_profile() -> None:
    # Given: full neutral feature evidence but no benchmark-relative strength.
    feature_input = _input(
        120,
        missing_relative_strength=frozenset({"rs_20d", "rs_60d"}),
    )

    # When: the completeness policy evaluates the snapshot.
    result = evaluate_feature_completeness(feature_input)

    # Then: neutral and relative-strength outcomes remain distinct.
    assert result.neutral_status is CompletenessStatus.COMPLETE
    assert result.relative_strength_status is CompletenessStatus.INCOMPLETE
    assert result.missing_relative_strength_fields == ("rs_20d", "rs_60d")


def test_stale_snapshot_cannot_satisfy_a_profile() -> None:
    # Given: all values and history exist but the source bar is not exact-date.
    feature_input = _input(252, exact_date=False)

    # When: the completeness policy evaluates the snapshot.
    result = evaluate_feature_completeness(feature_input)

    # Then: the profile fails closed on stale evidence.
    assert result.neutral_status is CompletenessStatus.INCOMPLETE
    assert result.freshness_issue == "STALE_DATE"


def test_snapshot_store_persists_profile_evidence() -> None:
    # Given: a migrated warehouse and evaluated STANDARD_120 evidence.
    conn = duckdb.connect()
    run_migrations(conn)

    # When: the feature snapshot is persisted.
    save_feature_snapshot(
        conn,
        "FPT",
        "2026-07-15",
        {"close": 100.0},
        {
            "feature_profile": "STANDARD_120",
            "neutral_completeness": "COMPLETE",
            "relative_strength_completeness": "INCOMPLETE",
            "required_bar_count": 120,
            "observed_bar_count": 120,
            "missing_neutral_fields_json": "[]",
            "missing_relative_strength_fields_json": '["rs_20d", "rs_60d"]',
            "feature_completeness_rule_version": "feature-completeness-v1",
        },
    )

    # Then: every evidence field is available to feature consumers.
    row = conn.execute(
        """
        SELECT feature_profile, neutral_completeness,
               relative_strength_completeness, required_bar_count,
               observed_bar_count, feature_completeness_rule_version
        FROM feature_snapshot
        WHERE symbol = 'FPT' AND date = '2026-07-15'
        """
    ).fetchone()
    assert row == (
        "STANDARD_120",
        "COMPLETE",
        "INCOMPLETE",
        120,
        120,
        "feature-completeness-v1",
    )


def test_scoring_rejects_legacy_feature_snapshot() -> None:
    # Given: a persisted row whose feature values predate profile evidence.
    conn = duckdb.connect()
    run_migrations(conn)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, feature_profile, neutral_completeness,
            relative_strength_completeness, as_of_bar_date, feature_data_status
        ) VALUES ('FPT', '2026-07-15', 100.0, 'LEGACY_UNKNOWN',
                  'LEGACY_UNKNOWN', 'LEGACY_UNKNOWN', '2026-07-15', 'EXACT_DATE')
        """
    )

    # When: the scoring boundary requests usable feature evidence.
    scored_count = score_universe(conn, "2026-07-15", universe=["FPT"])

    # Then: row existence alone cannot produce a candidate score.
    assert scored_count == 0


def test_breadth_rejects_legacy_snapshot_with_populated_fields() -> None:
    # Given: a legacy exact-date row containing the fields breadth would read.
    conn = duckdb.connect()
    run_migrations(conn)
    as_of_date = date(2026, 7, 15)
    upsert_symbol(conn, "FPT")
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, close, ma20, ma50, return_20d, as_of_bar_date,
            feature_data_status, feature_profile, neutral_completeness
        ) VALUES ('FPT', ?, 101.0, 100.0, 100.0, 0.01, ?, 'EXACT_DATE',
                  'LEGACY_UNKNOWN', 'LEGACY_UNKNOWN')
        """,
        [as_of_date, as_of_date],
    )

    # When: benchmark-neutral breadth requests usable minimum evidence.
    context = load_breadth_context(conn, as_of_date, "VNINDEX")

    # Then: row existence and populated fields do not make it eligible.
    assert context.eligible_count == 0


def test_readiness_evidence_rejects_legacy_feature_snapshot() -> None:
    # Given: a legacy feature row for the requested exact date.
    conn = duckdb.connect()
    run_migrations(conn)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, as_of_bar_date, feature_data_status, feature_profile,
            neutral_completeness, relative_strength_completeness
        ) VALUES ('FPT', '2026-07-15', '2026-07-15', 'EXACT_DATE',
                  'LEGACY_UNKNOWN', 'LEGACY_UNKNOWN', 'LEGACY_UNKNOWN')
        """
    )

    # When: readiness reads feature artifact evidence.
    evidence = get_feature_snapshot_evidence(conn, "FPT", "2026-07-15")

    # Then: an unqualified row is unavailable rather than ready.
    assert evidence.available is False
    assert evidence.quality_status == "INCOMPLETE_FEATURE_PROFILE"
