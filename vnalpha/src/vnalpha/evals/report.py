"""Immutable runtime reports and stable plain-text rendering for golden runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vnalpha.evals.contracts import EvaluationResult


@dataclass(frozen=True, slots=True)
class EvaluatedCase:
    """One successfully loaded fixture evaluated by the pure check suite."""

    path: Path
    case_id: str
    result: EvaluationResult


@dataclass(frozen=True, slots=True)
class RunFailure:
    """One discovery, load, adapter, duplicate, or check failure."""

    path: Path
    case_id: str | None
    check_name: str
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class EvaluationRunReport:
    """Complete immutable result for a deterministic offline corpus run."""

    source_count: int
    evaluations: tuple[EvaluatedCase, ...]
    failures: tuple[RunFailure, ...]

    @property
    def case_count(self) -> int:
        """Return the number of independently evaluated fixture files."""

        return len(self.evaluations)

    @property
    def operational_failure_count(self) -> int:
        """Return failures raised before or outside pure case checks."""

        return len(self.failures)

    @property
    def check_failure_count(self) -> int:
        """Return failed pure checks from evaluated cases."""

        return sum(
            not check.passed
            for evaluation in self.evaluations
            for check in evaluation.result.checks
        )

    @property
    def failed_case_count(self) -> int:
        """Return evaluated cases with either a check or operational failure."""

        failed_paths = {failure.path for failure in self.failures}
        return sum(
            not evaluation.result.passed or evaluation.path in failed_paths
            for evaluation in self.evaluations
        )

    @property
    def passed_case_count(self) -> int:
        """Return evaluated cases without any associated failure."""

        return self.case_count - self.failed_case_count

    @property
    def failure_count(self) -> int:
        """Return the total number of operational and check failures."""

        return self.operational_failure_count + self.check_failure_count

    @property
    def passed(self) -> bool:
        """Return whether the run contains no failure of any kind."""

        return self.failure_count == 0

    def all_failures(self) -> tuple[RunFailure, ...]:
        """Return every reportable failure in stable path/case/check order."""

        check_failures = tuple(
            RunFailure(
                path=evaluation.path,
                case_id=failure.case_id,
                check_name=failure.check_name,
                expected=failure.expected,
                actual=failure.actual,
            )
            for evaluation in self.evaluations
            for check in evaluation.result.checks
            if check.failure is not None
            for failure in (check.failure,)
        )
        return tuple(
            sorted(
                (*self.failures, *check_failures),
                key=lambda failure: (
                    failure.path.as_posix(),
                    failure.case_id or "",
                    failure.check_name,
                    failure.expected,
                    failure.actual,
                ),
            )
        )


def render_report(report: EvaluationRunReport) -> tuple[str, ...]:
    """Render stable human-readable detail lines followed by one total line."""

    detail_lines = tuple(
        "FAIL "
        f"path={failure.path.as_posix()} "
        f"case={failure.case_id or '-'} "
        f"check={failure.check_name} "
        f"expected={failure.expected} "
        f"actual={failure.actual}"
        for failure in report.all_failures()
    )
    return (*detail_lines, "SUMMARY " + _summary(report))


def _summary(report: EvaluationRunReport) -> str:
    return (
        f"discovered_fixtures={report.source_count} "
        f"evaluated_cases={report.case_count} "
        f"passed_evaluated_cases={report.passed_case_count} "
        f"failed_evaluated_cases={report.failed_case_count} "
        f"operational_failures={report.operational_failure_count} "
        f"check_failures={report.check_failure_count} "
        f"failures={report.failure_count}"
    )
