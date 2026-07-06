"""Normalization utilities for command parser inputs."""

from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.core.dates import resolve_date
from vnalpha.core.types import CANONICAL_CANDIDATE_CLASSES, CANONICAL_SETUP_TYPES


def normalize_symbol(value: str) -> str:
    """Normalize a stock symbol to uppercase stripped string."""
    return value.strip().upper()


def normalize_symbols(values: list[str]) -> list[str]:
    """Normalize a list of symbols."""
    return [normalize_symbol(v) for v in values]


def normalize_candidate_class(value: str) -> str:
    """Validate and normalize a candidate class value.

    Raises CommandValidationError if not a canonical value.
    """
    normalized = value.strip().upper()
    if normalized not in CANONICAL_CANDIDATE_CLASSES:
        raise CommandValidationError(
            f"Unknown candidate class: {value!r}. "
            f"Valid values: {sorted(CANONICAL_CANDIDATE_CLASSES)}"
        )
    return normalized


def normalize_setup_type(value: str) -> str:
    """Validate and normalize a setup type value.

    Raises CommandValidationError if not a canonical value.
    """
    normalized = value.strip().upper()
    if normalized not in CANONICAL_SETUP_TYPES:
        raise CommandValidationError(
            f"Unknown setup type: {value!r}. "
            f"Valid values: {sorted(CANONICAL_SETUP_TYPES)}"
        )
    return normalized


def normalize_date(value: str | None) -> str:
    """Resolve and normalize a date value.

    Delegates to core.dates.resolve_date.
    Raises CommandValidationError on invalid input.
    """
    try:
        return resolve_date(value)
    except (ValueError, TypeError) as exc:
        raise CommandValidationError(str(exc)) from exc
