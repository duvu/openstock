"""Frozen runtime contracts for deterministic golden-case evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from vnalpha.evals.identifiers import ArtifactId, ClaimId, FactId


class InvalidEvaluationObservationError(ValueError):
    """Raised when an observation repeats a claim or fact identity."""


@dataclass(frozen=True, slots=True)
class ObservedAnswerClaim:
    """One observed answer claim linked to static fact identities."""

    claim_id: ClaimId
    fact_ids: tuple[FactId, ...]

    def __post_init__(self) -> None:
        _require_unique(self.fact_ids, "observed fact_id")


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    """Typed local input to pure golden-case checks."""

    answer_text: str
    caveats: tuple[str, ...]
    missing_data: tuple[str, ...]
    observed_claims: tuple[ObservedAnswerClaim, ...]
    artifact_references: tuple[ArtifactId, ...]
    refused: bool
    reframed: bool

    def __post_init__(self) -> None:
        _require_unique(
            tuple(claim.claim_id for claim in self.observed_claims),
            "observed claim_id",
        )


@dataclass(frozen=True, slots=True)
class CheckFailure:
    """Actionable detail for one failed pure evaluation check."""

    case_id: str
    check_name: str
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome for one named check."""

    name: str
    failure: CheckFailure | None = None

    @property
    def passed(self) -> bool:
        """Return whether this check emitted no failure."""

        return self.failure is None


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Aggregate check outcome with a hard policy gate."""

    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        """Return whether all checks, including policy, passed."""

        return all(check.passed for check in self.checks) and self.policy_passed

    @property
    def policy_passed(self) -> bool:
        """Return the hard policy gate result."""

        return self.failure_for("policy") is None

    def failure_for(self, check_name: str) -> CheckFailure | None:
        """Return the diagnostic for one named check, when present."""

        for check in self.checks:
            if check.name == check_name:
                return check.failure
        return None


def failed_check(
    case_id: str, check_name: str, expected: str, actual: str
) -> CheckResult:
    """Build a failed check result with complete actionable diagnostics."""

    return CheckResult(
        name=check_name,
        failure=CheckFailure(
            case_id=case_id,
            check_name=check_name,
            expected=expected,
            actual=actual,
        ),
    )


def _require_unique(values: tuple[str, ...], name: str) -> None:
    for value in values:
        if values.count(value) > 1:
            raise InvalidEvaluationObservationError(f"duplicate {name}: {value}")
