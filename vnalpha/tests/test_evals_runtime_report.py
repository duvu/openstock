from __future__ import annotations

import json


def test_runtime_report_when_results_are_unsorted_renders_canonical_text_and_json() -> (
    None
):
    # Given: passing and failing replay cases supplied out of identifier order
    from vnalpha.evals.runtime_report import (
        RuntimeCheckResult,
        RuntimeReplayCaseResult,
        RuntimeReplayReport,
        render_runtime_report,
        runtime_report_json,
    )

    report = RuntimeReplayReport(
        source_count=2,
        cases=(
            RuntimeReplayCaseResult(
                case_id="zeta",
                checks=(RuntimeCheckResult("intent", '"expected"', '"actual"'),),
            ),
            RuntimeReplayCaseResult(
                case_id="alpha",
                checks=(RuntimeCheckResult("intent", '"same"', '"same"'),),
            ),
        ),
    )

    # When: human and machine reports are rendered repeatedly
    human = render_runtime_report(report)
    first_json = runtime_report_json(report)
    second_json = runtime_report_json(report)

    # Then: order, totals, schema, and serialization remain byte-stable
    assert human == (
        "PASS case=alpha checks=1",
        'FAIL case=zeta check=intent expected="expected" actual="actual"',
        "SUMMARY mode=runtime-replay discovered_cases=2 passed_cases=1 "
        "failed_cases=1 failures=1",
    )
    assert first_json == second_json
    payload = json.loads(first_json)
    assert payload["schema_version"] == 1
    assert [case["case_id"] for case in payload["cases"]] == ["alpha", "zeta"]
    assert payload["summary"] == {
        "discovered_cases": 2,
        "failed_cases": 1,
        "failures": 1,
        "passed_cases": 1,
    }
