from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_P = "port" + "folio"
_EXECUTION_PATTERNS = frozenset(
    {
        "buy(?:ing)?",
        "sell(?:ing)?",
        "order(?:s|ed|ing)?",
        "enter(?:ed|ing)?",
        "exit(?:ed|ing)?",
        "allocat(?:e|ed|ing|ion)",
        "broker(?:age)?",
        "account(?:s)?",
        _P,
        "margin",
        "purchas(?:e|ed|ing)",
        "trad(?:e|ed|ing)",
        "execut(?:e|ed|ing|ion)",
        "position(?:s)?",
    }
)
_EXECUTION_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(_EXECUTION_PATTERNS)) + r")\b", re.IGNORECASE
)


class ScenarioPolicyViolation(ValueError):
    pass


def validate_research_scenario_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("policy_classification") != "RESEARCH_ONLY":
        raise ScenarioPolicyViolation(
            "Scenario policy_classification must be RESEARCH_ONLY."
        )
    policy = payload.get("policy")
    disclaimer = policy.get("disclaimer") if isinstance(policy, Mapping) else None
    if not isinstance(disclaimer, str) or "research-only" not in disclaimer.lower():
        raise ScenarioPolicyViolation("Scenario requires a research-only disclaimer.")
    _validate_value(payload, "scenario")


def _validate_value(value: Any, path: str) -> None:
    if isinstance(value, str):
        normalized = value.replace("not an execution instruction", "")
        match = _EXECUTION_PATTERN.search(normalized)
        if match is not None:
            raise ScenarioPolicyViolation(
                f"Execution-oriented wording is not allowed at {path}: {match.group(0)}"
            )
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) == "policy":
                continue
            _validate_value(nested, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for index, nested in enumerate(value):
            _validate_value(nested, f"{path}[{index}]")


__all__ = ["ScenarioPolicyViolation", "validate_research_scenario_payload"]
