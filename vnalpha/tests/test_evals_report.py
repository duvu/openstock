from __future__ import annotations

from pathlib import Path

from vnalpha.evals.contracts import CheckFailure, CheckResult, EvaluationResult


def test_render_report_when_check_fails_includes_diagnostic_and_stable_totals() -> None:
    # Given: one immutable evaluated case containing a complete check failure
    from vnalpha.evals.report import EvaluatedCase, EvaluationRunReport, render_report

    result = EvaluationResult(
        checks=(
            CheckResult(
                name="policy",
                failure=CheckFailure(
                    case_id="unsafe_case",
                    check_name="policy",
                    expected="research-only answer",
                    actual="buy now",
                ),
            ),
        )
    )
    report = EvaluationRunReport(
        source_count=1,
        evaluations=(
            EvaluatedCase(
                path=Path("research_answers/unsafe.yaml"),
                case_id="unsafe_case",
                result=result,
            ),
        ),
        failures=(),
    )

    # When: the report is rendered for a terminal surface
    output = "\n".join(render_report(report))

    # Then: path, case, check, expected/actual values, and totals are explicit
    assert "path=research_answers/unsafe.yaml" in output
    assert "case=unsafe_case" in output
    assert "check=policy" in output
    assert "expected=research-only answer" in output
    assert "actual=buy now" in output
    assert (
        "discovered_fixtures=1 evaluated_cases=1 passed_evaluated_cases=0 "
        "failed_evaluated_cases=1 operational_failures=0 check_failures=1 failures=1"
        in output
    )
