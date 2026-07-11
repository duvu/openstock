from __future__ import annotations

import pytest

from vnalpha.research_intelligence.scenario_policy import (
    RESEARCH_ONLY_DISCLAIMER,
    ScenarioLanguageValidationError,
    validate_research_only_language,
)


@pytest.mark.parametrize(
    "instruction",
    [
        "Place stop at 100.",
        "Order 100 shares.",
        "Enter FPT.",
        "Exit FPT.",
        "Allocate 10 percent.",
        "Use margin.",
        "Purchase FPT now.",
        "Trade FPT now.",
        "Short FPT now.",
        "Open a position in FPT.",
        "Invest in FPT now.",
        "Go long FPT.",
        "Set a stop-loss at 100.",
        "Liquidate FPT now.",
        "Add FPT to your holdings.",
        "Hold FPT.",
        "Recommend FPT.",
        "Close a position in FPT.",
        "Establish a position in FPT.",
        "Rebalance your holdings.",
    ],
)
def test_validator_rejects_each_execution_instruction_term(instruction: str) -> None:
    with pytest.raises(ScenarioLanguageValidationError):
        validate_research_only_language(
            {
                "summary": instruction,
                "research_only_language": RESEARCH_ONLY_DISCLAIMER,
            }
        )
