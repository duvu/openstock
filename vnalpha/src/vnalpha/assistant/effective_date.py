from __future__ import annotations

from vnalpha.assistant.errors import AssistantInputValidationError
from vnalpha.core.dates import resolve_date, resolve_market_session_date

_CURRENT_SYMBOL_SESSION_INTENTS = frozenset({"deep_analyze_symbol"})


def normalize_date_candidate(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def validate_date_candidate(value: str | None) -> None:
    if value is None:
        return
    try:
        resolve_date(value)
    except ValueError as exc:
        raise AssistantInputValidationError(
            f"Invalid date value {value!r}; expected 'today' or ISO format YYYY-MM-DD."
        ) from exc


def resolve_effective_target_date(
    *,
    classified_date: str | None,
    request_date: str | None,
    intent: str | None = None,
    request_date_is_implicit: bool = False,
) -> str:
    classified = normalize_date_candidate(classified_date)
    requested = normalize_date_candidate(request_date)
    selected = classified if classified is not None else requested
    validate_date_candidate(selected)
    try:
        if intent in _CURRENT_SYMBOL_SESSION_INTENTS:
            current_symbol_date = (
                None if classified is None and request_date_is_implicit else selected
            )
            return resolve_market_session_date(current_symbol_date)
        return resolve_date(selected)
    except ValueError as exc:
        raise AssistantInputValidationError(str(exc)) from exc


__all__ = [
    "normalize_date_candidate",
    "resolve_effective_target_date",
    "validate_date_candidate",
]
