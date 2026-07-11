from __future__ import annotations

import pytest


def test_research_only_language_validator_accepts_required_disclaimer() -> None:
    from vnalpha.research_intelligence.scenario_policy import (
        RESEARCH_ONLY_DISCLAIMER,
        validate_research_only_language,
    )

    validate_research_only_language(
        {
            "current_setup": "Observed trend and volume context.",
            "research_only_language": RESEARCH_ONLY_DISCLAIMER,
        }
    )


@pytest.mark.parametrize(
    "text",
    [
        "Buy FPT now.",
        "Place an order after confirmation.",
        "Allocate capital to this idea.",
    ],
)
def test_research_only_language_validator_rejects_execution_instruction(
    text: str,
) -> None:
    from vnalpha.research_intelligence.scenario_policy import (
        RESEARCH_ONLY_DISCLAIMER,
        ScenarioLanguageValidationError,
        validate_research_only_language,
    )

    with pytest.raises(ScenarioLanguageValidationError):
        validate_research_only_language(
            {"summary": text, "research_only_language": RESEARCH_ONLY_DISCLAIMER}
        )
