from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnalpha.assistant.groundedness import validate_research_answer
from vnalpha.assistant.models import AssistantAnswer, AssistantPlan, ToolPlanStep


FIXTURE = Path(__file__).parent / "fixtures" / "research_intelligence_golden.jsonl"


def _cases() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["case_id"])
def test_research_intelligence_golden_case(case: dict) -> None:
    plan = AssistantPlan(
        intent=case["intent"],
        steps=[
            ToolPlanStep(
                step_id="shortlist-1",
                tool_name="shortlist.generate",
                arguments={"date": "2026-07-01", "limit": 5},
                purpose="research shortlist",
                required_permission="READ_WATCHLIST",
            )
        ],
        required_artifacts=["daily_watchlist", "candidate_score"],
    )
    status = case.get("tool_status", "READY")
    outputs = {
        "shortlist-1": {
            "data": {
                "status": status,
                "as_of_date": "2026-07-01",
                "methodology": {"version": "v1"},
                "candidates": [{"symbol": "FPT", "shortlist_score": 0.81}]
                if status == "READY"
                else [],
                "artifact_refs": ["daily_watchlist:2026-07-01"],
                "freshness": {"watchlist_date": "2026-07-01"},
                "caveats": ["Research prioritization requires human review."],
                "missing_data": []
                if status == "READY"
                else ["matching candidates"],
            },
            "summary": "Research shortlist payload.",
            "warnings": [],
        }
    }
    answer = AssistantAnswer(
        summary=case["summary"],
        basis=case["basis"],
        risks_caveats=case["risks_caveats"],
        tool_trace_summary="Used shortlist.generate.",
        missing_data=case["missing_data"],
    )

    result = validate_research_answer(plan, outputs, answer)

    assert result.status == case["expected_status"]
