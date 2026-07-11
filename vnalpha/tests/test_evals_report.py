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


def test_render_report_when_operational_and_check_failures_are_unsorted_orders_all_details(
) -> None:
    # Given: unsorted operational failures and check failures across three source fixtures
    from vnalpha.evals.report import (
        EvaluatedCase,
        EvaluationRunReport,
        RunFailure,
        render_report,
    )

    alpha_result = EvaluationResult(
        checks=(
            CheckResult(
                name="groundedness",
                failure=CheckFailure(
                    case_id="alpha",
                    check_name="groundedness",
                    expected="summary",
                    actual="missing",
                ),
            ),
        )
    )
    beta_result = EvaluationResult(
        checks=(
            CheckResult(
                name="policy",
                failure=CheckFailure(
                    case_id="beta",
                    check_name="policy",
                    expected="safe answer",
                    actual="buy now",
                ),
            ),
        )
    )
    report = EvaluationRunReport(
        source_count=3,
        evaluations=(
            EvaluatedCase(Path("research_answers/b.yaml"), "beta", beta_result),
            EvaluatedCase(Path("research_answers/a.yaml"), "alpha", alpha_result),
        ),
        failures=(
            RunFailure(Path("research_answers/c.yaml"), None, "load", "YAML", "invalid"),
            RunFailure(Path("research_answers/a.yaml"), None, "adapter", "valid", "invalid"),
        ),
    )

    # When: the immutable report renders its combined failure list
    output = render_report(report)

    # Then: lines sort by path, case, and check before an unambiguous total line
    assert output == (
        "FAIL path=research_answers/a.yaml case=- check=adapter expected=valid actual=invalid",
        "FAIL path=research_answers/a.yaml case=alpha check=groundedness expected=summary actual=missing",
        "FAIL path=research_answers/b.yaml case=beta check=policy expected=safe answer actual=buy now",
        "FAIL path=research_answers/c.yaml case=- check=load expected=YAML actual=invalid",
        "SUMMARY discovered_fixtures=3 evaluated_cases=2 passed_evaluated_cases=0 "
        "failed_evaluated_cases=2 operational_failures=2 check_failures=2 failures=4",
    )


def test_render_report_when_only_load_failure_labels_operational_failure() -> None:
    # Given: a discovered fixture that failed before evaluation
    from vnalpha.evals.report import EvaluationRunReport, RunFailure, render_report

    report = EvaluationRunReport(
        source_count=1,
        evaluations=(),
        failures=(RunFailure(Path("research_answers/broken.yaml"), None, "load", "YAML", "invalid"),),
    )

    # When: the report renders the malformed-only corpus result
    output = render_report(report)

    # Then: zero evaluated failures cannot conceal the operational failure
    assert output[-1] == (
        "SUMMARY discovered_fixtures=1 evaluated_cases=0 passed_evaluated_cases=0 "
        "failed_evaluated_cases=0 operational_failures=1 check_failures=0 failures=1"
    )
