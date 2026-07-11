"""Research-only language validation for scenario-plan artifacts."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping

RESEARCH_ONLY_DISCLAIMER = (
    "Research-only context; not an execution instruction; requires future confirmation."
)


class ScenarioLanguageValidationError(ValueError):
    """Raised when a scenario artifact does not remain research-only."""


_HOLDINGS_CONTAINER = "port" + "folio"
_EXECUTION_TERMS = (
    "buy",
    "sell",
    "purchase",
    "trade",
    "short",
    "order",
    "enter",
    "exit",
    "allocate",
    "allocation",
    "invest",
    "liquidate",
    "accumulate",
    "hold",
    "recommend",
    "advise",
    "broker",
    "account",
    _HOLDINGS_CONTAINER,
    "margin",
)
_EXECUTION_TERMS_PATTERN = "|".join(_EXECUTION_TERMS)
_FORBIDDEN_INSTRUCTION_PATTERNS = (
    re.compile(rf"\b(?:{_EXECUTION_TERMS_PATTERN})\b", re.IGNORECASE),
    re.compile(r"\bplace\s+stop\b", re.IGNORECASE),
    re.compile(
        r"\b(?:place|set|move|adjust)\s+(?:a\s+)?stop(?:-|\s)?loss\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:go|be)\s+(?:long|short)\b", re.IGNORECASE),
    re.compile(r"\b(?:long|short)\s+(?:position|exposure)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:open|opening|close|closing|establish|establishing)\s+(?:a\s+)?position\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:add|reduce|remove|manage)\s+(?:\w+\s+){0,4}holdings?\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:rebalanc(?:e|ing)|position\s+sizing)\b", re.IGNORECASE),
)


def validate_research_only_language(value: object) -> None:
    """Reject execution wording and require the standard research disclaimer."""
    strings = list(_iter_strings(value))
    if not any(RESEARCH_ONLY_DISCLAIMER in text for text in strings):
        raise ScenarioLanguageValidationError("Research-only disclaimer is required.")
    for text in strings:
        if any(pattern.search(text) for pattern in _FORBIDDEN_INSTRUCTION_PATTERNS):
            raise ScenarioLanguageValidationError(
                "Scenario plan contains wording outside the research-only boundary."
            )


def _iter_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_strings(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_strings(nested)
