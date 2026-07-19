from __future__ import annotations

from vnalpha.assistant.errors import AssistantInputValidationError
from vnalpha.core.dates import resolve_date


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
    *, classified_date: str | None, request_date: str | None
) -> str:
    classified = normalize_date_candidate(classified_date)
    requested = normalize_date_candidate(request_date)
    selected = classified if classified is not None else requested
    validate_date_candidate(selected)
    return resolve_date(selected)


__all__ = [
    "normalize_date_candidate",
    "resolve_effective_target_date",
    "validate_date_candidate",
]
