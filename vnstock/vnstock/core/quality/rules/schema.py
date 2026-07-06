"""Schema validation rules for market data DataFrames.

Each function accepts a DataFrame and returns a list of
:class:`~vnstock.core.quality.models.QualityIssue` objects.
"""

from __future__ import annotations

import pandas as pd

from vnstock.core.quality.models import QualityIssue


def check_required_columns(
    df: pd.DataFrame,
    required: list[str],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return an error issue for each required column that is absent.

    Args:
        df: DataFrame to inspect.
        required: List of column names that must be present.
        max_examples: Not used for column checks; kept for API consistency.

    Returns:
        List of :class:`QualityIssue` with code ``SCHEMA_MISSING_COLUMN``.
    """
    issues: list[QualityIssue] = []
    for col in required:
        if col not in df.columns:
            issues.append(
                QualityIssue(
                    code="SCHEMA_MISSING_COLUMN",
                    severity="error",
                    message=f"Required column '{col}' is missing.",
                    column=col,
                )
            )
    return issues


def check_empty_dataframe(df: pd.DataFrame) -> list[QualityIssue]:
    """Return an error issue when the DataFrame has no rows.

    Args:
        df: DataFrame to inspect.

    Returns:
        List containing one :class:`QualityIssue` with code
        ``SCHEMA_EMPTY_DATAFRAME`` when ``len(df) == 0``, otherwise empty.
    """
    if df.empty:
        return [
            QualityIssue(
                code="SCHEMA_EMPTY_DATAFRAME",
                severity="error",
                message="DataFrame is empty (zero rows).",
            )
        ]
    return []


def check_dtypes(
    df: pd.DataFrame,
    expected_kinds: dict[str, str | tuple[str, ...]],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Validate that columns have the expected pandas dtype kind.

    ``expected_kinds`` maps column name → dtype kind character(s) from
    `numpy dtype.kind <https://numpy.org/doc/stable/reference/generated/numpy.dtype.kind.html>`_:

    * ``"f"`` — floating-point
    * ``"i"`` / ``"u"`` — signed / unsigned integer
    * ``"M"`` — datetime64
    * ``"O"`` — object
    * ``"b"`` — boolean

    Pass a tuple to allow multiple kinds, e.g. ``("f", "i", "u")`` for
    any numeric column.

    Args:
        df: DataFrame to inspect.
        expected_kinds: Mapping ``{column: kind_or_tuple_of_kinds}``.
        max_examples: Maximum number of dtype issues to return.

    Returns:
        List of :class:`QualityIssue` with code ``SCHEMA_INVALID_DTYPE``.
    """
    issues: list[QualityIssue] = []
    for col, kinds in expected_kinds.items():
        if col not in df.columns:
            continue  # missing-column handled by check_required_columns
        actual_kind = df[col].dtype.kind
        allowed = (kinds,) if isinstance(kinds, str) else tuple(kinds)
        if actual_kind not in allowed:
            issues.append(
                QualityIssue(
                    code="SCHEMA_INVALID_DTYPE",
                    severity="warning",
                    message=(
                        f"Column '{col}' has dtype kind '{actual_kind}' "
                        f"but expected one of {allowed}."
                    ),
                    column=col,
                    context={
                        "actual_kind": actual_kind,
                        "expected_kinds": list(allowed),
                    },
                )
            )
        if len(issues) >= max_examples:
            break
    return issues


def check_all_null_columns(
    df: pd.DataFrame,
    columns: list[str],
    max_examples: int = 20,
) -> list[QualityIssue]:
    """Return a warning issue for each column that is entirely null/NaN.

    Args:
        df: DataFrame to inspect.
        columns: List of column names to check.
        max_examples: Maximum number of issues to return.

    Returns:
        List of :class:`QualityIssue` with code ``SCHEMA_COLUMN_ALL_NULL``.
    """
    issues: list[QualityIssue] = []
    for col in columns:
        if col not in df.columns:
            continue
        if df[col].isna().all():
            issues.append(
                QualityIssue(
                    code="SCHEMA_COLUMN_ALL_NULL",
                    severity="warning",
                    message=f"Column '{col}' is entirely null/NaN.",
                    column=col,
                )
            )
        if len(issues) >= max_examples:
            break
    return issues
