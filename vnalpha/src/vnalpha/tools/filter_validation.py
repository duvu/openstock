"""Shared filter validation for watchlist.filter tool and /filter handler."""

from __future__ import annotations

# Canonical set of supported filter field names (including user-friendly aliases)
SUPPORTED_FILTER_FIELDS: frozenset[str] = frozenset(
    {
        "score",
        "candidate_class",
        "class",  # alias for candidate_class
        "setup_type",
        "setup",  # alias for setup_type
        "rank",
        "risk_flags",
        "data_quality_status",
        "symbol",
    }
)

# Fields that require numeric comparison values with inequality operators
NUMERIC_FIELDS: frozenset[str] = frozenset({"score", "rank"})

# Operators that trigger numeric value requirement
NUMERIC_OPS: frozenset[str] = frozenset({">", ">=", "<", "<="})


class FilterValidationError(ValueError):
    """Raised when a filter expression fails validation."""


def validate_filters(filters: list[dict]) -> None:
    """Validate a list of filter dicts against the canonical schema.

    Each dict must have keys: ``key``, ``op``, ``value``.

    Raises:
        FilterValidationError: if any filter is invalid.
    """
    for item in filters:
        key = str(item.get("key", ""))
        op = str(item.get("op", ""))
        value = str(item.get("value", ""))

        if key not in SUPPORTED_FILTER_FIELDS:
            raise FilterValidationError(
                f"Unsupported filter field: '{key}'. "
                f"Supported fields: {sorted(SUPPORTED_FILTER_FIELDS)}"
            )
        if key in NUMERIC_FIELDS and op in NUMERIC_OPS:
            try:
                float(value)
            except ValueError as err:
                raise FilterValidationError(
                    f"Filter '{key}{op}{value}' requires a numeric value, got '{value}'."
                ) from err
