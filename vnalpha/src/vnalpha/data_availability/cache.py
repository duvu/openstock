"""Typed cache-hit eligibility policy."""

from __future__ import annotations

from datetime import date as DateType
from typing import Protocol

from vnalpha.data_availability.models import CacheEligibility
from vnalpha.data_availability.policy import DataAvailabilityPolicy


class CacheEvidenceSnapshot(Protocol):
    target_date: str
    canonical_bars: int
    benchmark_bars: int
    feature_snapshot_exists: bool
    candidate_score_exists: bool
    candidate_score_as_of_date: str | None
    quality_status: str | None
    lineage_fields: frozenset[str]


def evaluate_cache_eligibility(
    snapshot: CacheEvidenceSnapshot,
    policy: DataAvailabilityPolicy,
) -> CacheEligibility:
    """Evaluate every persisted artifact required for a cache hit."""

    score_fresh = _score_is_fresh(snapshot, policy)
    feature_present = snapshot.feature_snapshot_exists
    canonical_sufficient = snapshot.canonical_bars >= policy.min_required_bars
    benchmark_sufficient = (
        not policy.require_benchmark_history
        or snapshot.benchmark_bars >= policy.min_required_bars
    )
    acceptable_quality = {
        value.strip().lower() for value in policy.acceptable_quality_statuses
    }
    quality_acceptable = (
        snapshot.quality_status is not None
        and snapshot.quality_status.strip().lower() in acceptable_quality
    )
    lineage_acceptable = set(policy.required_lineage_fields).issubset(
        snapshot.lineage_fields
    )

    reasons: list[str] = []
    if not snapshot.candidate_score_exists:
        reasons.append("score_missing")
    elif not score_fresh:
        reasons.append("score_stale")
    if not feature_present:
        reasons.append("feature_snapshot_missing")
    if not canonical_sufficient:
        reasons.append("canonical_history_insufficient")
    if not benchmark_sufficient:
        reasons.append("benchmark_history_insufficient")
    if not quality_acceptable:
        reasons.append("quality_unacceptable")
    if not lineage_acceptable:
        reasons.append("lineage_incomplete")

    return CacheEligibility(
        eligible=not reasons,
        reasons=tuple(reasons),
        score_fresh=score_fresh,
        feature_present=feature_present,
        canonical_sufficient=canonical_sufficient,
        benchmark_sufficient=benchmark_sufficient,
        quality_acceptable=quality_acceptable,
        lineage_acceptable=lineage_acceptable,
    )


def _score_is_fresh(
    snapshot: CacheEvidenceSnapshot,
    policy: DataAvailabilityPolicy,
) -> bool:
    if not snapshot.candidate_score_exists:
        return False
    if snapshot.candidate_score_as_of_date is None:
        return False
    try:
        score_date = DateType.fromisoformat(snapshot.candidate_score_as_of_date)
        target_date = DateType.fromisoformat(snapshot.target_date)
    except ValueError:
        return False
    if score_date > target_date:
        return False
    if policy.stale_after_calendar_days <= 0:
        return True
    return (target_date - score_date).days <= policy.stale_after_calendar_days


__all__ = ["CacheEvidenceSnapshot", "evaluate_cache_eligibility"]
