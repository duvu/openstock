from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeCheckResult:
    name: str
    expected: str
    actual: str

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


@dataclass(frozen=True, slots=True)
class RuntimeReplayCaseResult:
    case_id: str
    checks: tuple[RuntimeCheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failure_count(self) -> int:
        return sum(not check.passed for check in self.checks)


@dataclass(frozen=True, slots=True)
class RuntimeReplayReport:
    source_count: int
    cases: tuple[RuntimeReplayCaseResult, ...]

    @property
    def passed_case_count(self) -> int:
        return sum(case.passed for case in self.cases)

    @property
    def failed_case_count(self) -> int:
        return len(self.cases) - self.passed_case_count

    @property
    def failure_count(self) -> int:
        return sum(case.failure_count for case in self.cases)

    @property
    def passed(self) -> bool:
        return self.source_count > 0 and self.failure_count == 0


def render_runtime_report(report: RuntimeReplayReport) -> tuple[str, ...]:
    lines: list[str] = []
    for case in sorted(report.cases, key=lambda item: item.case_id):
        if case.passed:
            lines.append(f"PASS case={case.case_id} checks={len(case.checks)}")
            continue
        lines.extend(
            f"FAIL case={case.case_id} check={check.name} "
            f"expected={check.expected} actual={check.actual}"
            for check in case.checks
            if not check.passed
        )
    lines.append(
        "SUMMARY mode=runtime-replay "
        f"discovered_cases={report.source_count} "
        f"passed_cases={report.passed_case_count} "
        f"failed_cases={report.failed_case_count} "
        f"failures={report.failure_count}"
    )
    return tuple(lines)


def runtime_report_json(report: RuntimeReplayReport) -> str:
    cases = tuple(sorted(report.cases, key=lambda item: item.case_id))
    payload = {
        "schema_version": 1,
        "mode": "runtime-replay",
        "summary": {
            "discovered_cases": report.source_count,
            "passed_cases": report.passed_case_count,
            "failed_cases": report.failed_case_count,
            "failures": report.failure_count,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "passed": case.passed,
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "expected": check.expected,
                        "actual": check.actual,
                    }
                    for check in case.checks
                ],
            }
            for case in cases
        ],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
