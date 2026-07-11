from __future__ import annotations

from typing import get_type_hints


def test_research_scenario_plan_declares_required_artifact_links() -> None:
    from vnalpha.research_intelligence.scenario_plan import ResearchScenarioPlan

    hints = get_type_hints(ResearchScenarioPlan)

    assert {
        "symbol",
        "as_of_date",
        "artifact_references",
        "correlation_id",
        "research_only_language",
    } <= set(hints)
