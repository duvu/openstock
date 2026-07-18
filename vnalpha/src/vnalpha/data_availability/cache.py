"""Typed cache-hit eligibility policy."""

from __future__ import annotations

from datetime import date as DateType
from typing import Protocol

from vnalpha.data_availability.models import CacheEligibility, EvidenceIssue
from vnalpha.data_availability.policy import DataAvailabilityPolicy


class CacheEvidenceSnapshot(Protocol):
    target_date: str
    canonical_bars: int
    benchmark_bars: int
    unresolved_true_gap_count: int
    feature_snapshot_exists: bool
    feature_snapshot_row_exists: bool | None
    feature_profile_acceptable: bool
    feature_lineage_acceptable: bool
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
    feature_row_exists = (
        snapshot.feature_snapshot_exists
        if snapshot.feature_snapshot_row_exists is None
        else snapshot.feature_snapshot_row_exists
    )
    feature_present = (
        snapshot.feature_snapshot_exists
        and snapshot.feature_profile_acceptable
        and snapshot.feature_lineage_acceptable
    )
    canonical_history_sufficient = snapshot.canonical_bars >= policy.min_required_bars
    canonical_gaps_resolved = snapshot.unresolved_true_gap_count == 0
    canonical_sufficient = canonical_history_sufficient and canonical_gaps_resolved
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

    issues: list[EvidenceIssue] = []
    if not snapshot.candidate_score_exists:
        issues.append(EvidenceIssue.SCORE_MISSING)
    elif not score_fresh:
        issues.append(EvidenceIssue.SCORE_STALE)
    if not feature_row_exists:
        issues.append(EvidenceIssue.FEATURE_SNAPSHOT_MISSING)
    elif not snapshot.feature_profile_acceptable:
        issues.append(EvidenceIssue.FEATURE_SNAPSHOT_INVALID)
    elif not snapshot.feature_lineage_acceptable:
        issues.append(EvidenceIssue.FEATURE_LINEAGE_INCOMPLETE)
    elif not snapshot.feature_snapshot_exists:
        issues.append(EvidenceIssue.FEATURE_SNAPSHOT_INVALID)
    if not canonical_history_sufficient:
        issues.append(EvidenceIssue.CANONICAL_HISTORY_INSUFFICIENT)
    if not canonical_gaps_resolved:
        issues.append(EvidenceIssue.CANONICAL_GAPS_UNRESOLVED)
    if not benchmark_sufficient:
        issues.append(EvidenceIssue.BENCHMARK_HISTORY_INSUFFICIENT)
    if not quality_acceptable:
        issues.append(EvidenceIssue.QUALITY_UNACCEPTABLE)
    if snapshot.candidate_score_exists and not lineage_acceptable:
        issues.append(EvidenceIssue.LINEAGE_INCOMPLETE)

    return CacheEligibility(
        eligible=not issues,
        reasons=tuple(issue.value for issue in issues),
        score_fresh=score_fresh,
        feature_present=feature_present,
        canonical_sufficient=canonical_sufficient,
        benchmark_sufficient=benchmark_sufficient,
        quality_acceptable=quality_acceptable,
        lineage_acceptable=lineage_acceptable,
        issues=tuple(issues),
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
