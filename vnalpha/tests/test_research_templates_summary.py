"""Regression coverage for the deterministic research-answer templates."""

from __future__ import annotations

from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
from vnalpha.assistant.research_templates import build_deterministic_research_answer


def _provisioning_payload() -> dict:
    """Shape of data.ensure_current_symbol's ToolOutput.data (to_trace_dict())."""
    return {
        "symbol": "FPT",
        "outcome": "READY",
        "correlation_id": "corr-1",
        "requested_date": None,
        "resolved_date": "2026-07-10",
        "reused_fresh_data": False,
        "refreshed": False,
        "actions": [{"action": "score_symbol", "status": "SUCCESS"}],
        "warnings": [],
        "errors": [],
        "remediation": [],
    }


def _deep_symbol_payload() -> dict:
    """Shape of analysis.deep_symbol's ToolOutput.data."""
    return {
        "tool": "analysis.deep_symbol",
        "available": True,
        "symbol": "FPT",
        "requested_date": None,
        "as_of_date": "2026-07-10",
        "candidate": {
            "score": 0.2199,
            "candidate_class": "IGNORE",
            "setup_type": "PULLBACK_TO_TREND",
        },
        "missing_data": [],
        "caveats": [],
        "artifact_refs": ["candidate_score:FPT:2026-07-10"],
    }


def _plan_with_provisioning_step() -> AssistantPlan:
    return AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT"},
                purpose="Provision data",
                required_permission="WRITE_DATA",
            ),
            ToolPlanStep(
                step_id="step_2",
                tool_name="analysis.deep_symbol",
                arguments={"symbol": "FPT"},
                purpose="Compose analysis",
                required_permission="READ_SCORE",
            ),
        ],
    )


def test_deep_analyze_summary_uses_analysis_payload_not_provisioning_payload() -> None:
    """The provisioning step's payload must never be mistaken for the
    analysis payload just because it runs first.

    Regression: _summary_for_intent always read payloads[0], which for
    deep_analyze_symbol is data.ensure_current_symbol's provisioning result
    (no candidate/as_of_date fields) rather than analysis.deep_symbol's
    result. Every deep-analysis answer rendered "score=None, class=None,
    setup=None" and "as of unknown" even when a real candidate score existed.
    """

    plan = _plan_with_provisioning_step()
    tool_outputs = {
        "step_1": {"data": _provisioning_payload()},
        "step_2": {"data": _deep_symbol_payload()},
    }

    answer = build_deterministic_research_answer(plan, tool_outputs)

    assert "score=0.2199" in answer.summary
    assert "class=IGNORE" in answer.summary
    assert "setup=PULLBACK_TO_TREND" in answer.summary
    assert "as of 2026-07-10" in answer.summary
    assert "as of unknown" not in answer.summary


def test_deep_analyze_summary_falls_back_gracefully_when_no_candidate_payload() -> None:
    """With no analysis payload present at all, the summary degrades to
    'unknown'/None rather than raising."""

    plan = AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT"},
                purpose="Provision data",
                required_permission="WRITE_DATA",
            )
        ],
    )
    tool_outputs = {"step_1": {"data": _provisioning_payload()}}

    answer = build_deterministic_research_answer(plan, tool_outputs)

    assert "score=None" in answer.summary
    assert "as of unknown" in answer.summary
