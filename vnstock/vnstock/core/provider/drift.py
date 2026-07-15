"""Schema drift detection for provider adapters.

Compares actual DataFrame output from providers against a stored baseline schema
(column names, dtypes, min/max row counts). Reports drift as ProviderIssue list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.api.types import is_string_dtype

from vnstock.core.provider.models import ProviderIssue


@dataclass
class ColumnSpec:
    """Expected spec for a single column."""

    name: str
    dtype: str  # pandas dtype name or prefix, e.g. "float64", "int64", "datetime"
    nullable: bool = False


@dataclass
class DatasetSchema:
    """Expected schema for a normalized dataset."""

    dataset_type: str
    provider: str
    columns: list[ColumnSpec] = field(default_factory=list)
    min_rows: int = 0
    max_rows: int | None = None


# --- Built-in baseline schemas ---

OHLCV_COLUMNS = [
    ColumnSpec("time", "datetime"),
    ColumnSpec("open", "float64"),
    ColumnSpec("high", "float64"),
    ColumnSpec("low", "float64"),
    ColumnSpec("close", "float64"),
    ColumnSpec("volume", "int64"),
]

INTRADAY_COLUMNS = [
    ColumnSpec("time", "datetime"),
    ColumnSpec("price", "float64"),
    ColumnSpec("volume", "int64"),
    ColumnSpec("match_type", "object"),
]

PRICE_BOARD_COLUMNS = [
    ColumnSpec("symbol", "object"),
    ColumnSpec("reference_price", "float64"),
    ColumnSpec("close_price", "float64"),
    ColumnSpec("volume_accumulated", "int64"),
]


def _baseline_schemas() -> dict[tuple[str, str], DatasetSchema]:
    """Return registry of baseline schemas keyed by (provider, dataset_type)."""
    schemas: dict[tuple[str, str], DatasetSchema] = {}
    for provider in ("dnse", "kbs", "vci", "tcbs"):
        schemas[(provider, "ohlcv")] = DatasetSchema(
            dataset_type="ohlcv",
            provider=provider,
            columns=OHLCV_COLUMNS,
            min_rows=1,
        )
        schemas[(provider, "intraday_trades")] = DatasetSchema(
            dataset_type="intraday_trades",
            provider=provider,
            columns=INTRADAY_COLUMNS,
            min_rows=1,
        )
        schemas[(provider, "price_board")] = DatasetSchema(
            dataset_type="price_board",
            provider=provider,
            columns=PRICE_BOARD_COLUMNS,
            min_rows=1,
        )
    return schemas


_BASELINE: dict[tuple[str, str], DatasetSchema] | None = None


def _get_baseline() -> dict[tuple[str, str], DatasetSchema]:
    global _BASELINE
    if _BASELINE is None:
        _BASELINE = _baseline_schemas()
    return _BASELINE


def _dtype_matches(series: pd.Series, expected_prefix: str) -> bool:
    """Match semantic string dtypes across supported pandas versions.

    Pandas 3 may infer textual columns as the dedicated ``str`` dtype while
    earlier versions report ``object``. The provider contract treats both as
    normalized text; numeric and datetime contracts remain exact/prefix based.
    """

    actual_dtype = str(series.dtype)
    if actual_dtype == expected_prefix or actual_dtype.startswith(expected_prefix):
        return True
    return expected_prefix == "object" and is_string_dtype(series.dtype)


def detect_drift(
    df: pd.DataFrame,
    provider: str,
    dataset_type: str,
    *,
    extra_schema: DatasetSchema | None = None,
) -> list[ProviderIssue]:
    """Detect schema drift between *df* and the stored baseline.

    Parameters
    ----------
    df:
        Normalized DataFrame returned by the provider adapter.
    provider:
        Provider name (case-insensitive): "dnse", "kbs", "vci", etc.
    dataset_type:
        Dataset type: "ohlcv", "intraday_trades", "price_board".
    extra_schema:
        Optional caller-supplied schema; takes precedence over built-in baselines.

    Returns
    -------
    list[ProviderIssue]
        Empty list means no drift detected.
    """
    provider_key = provider.lower() if isinstance(provider, str) else ""
    if not isinstance(df, pd.DataFrame):
        return [
            ProviderIssue(
                code="DRIFT_INVALID_INPUT",
                severity="error",
                provider=str(provider) if provider else "",
                capability=str(dataset_type) if dataset_type else "",
                message=(
                    f"detect_drift() requires a pandas DataFrame; "
                    f"got {type(df).__name__!r}."
                ),
            )
        ]
    if not isinstance(provider, str) or not provider.strip():
        return [
            ProviderIssue(
                code="DRIFT_INVALID_INPUT",
                severity="error",
                provider=str(provider) if provider else "",
                capability=str(dataset_type) if dataset_type else "",
                message="detect_drift() requires a non-empty provider string.",
            )
        ]
    schema = extra_schema or _get_baseline().get((provider_key, dataset_type))

    if schema is None:
        return [
            ProviderIssue(
                code="DRIFT_NO_BASELINE",
                severity="info",
                provider=provider,
                capability=dataset_type,
                message=(
                    f"No baseline schema registered for "
                    f"provider={provider!r} dataset_type={dataset_type!r}. "
                    "Drift detection skipped."
                ),
            )
        ]

    issues: list[ProviderIssue] = []

    # --- Row count check ---
    n_rows = len(df)
    if n_rows < schema.min_rows:
        issues.append(
            ProviderIssue(
                code="DRIFT_ROW_COUNT_LOW",
                severity="warning",
                provider=provider,
                capability=dataset_type,
                message=(
                    f"DataFrame has {n_rows} rows; expected at least {schema.min_rows}."
                ),
                context={"actual": n_rows, "minimum": schema.min_rows},
            )
        )
    if schema.max_rows is not None and n_rows > schema.max_rows:
        issues.append(
            ProviderIssue(
                code="DRIFT_ROW_COUNT_HIGH",
                severity="warning",
                provider=provider,
                capability=dataset_type,
                message=(
                    f"DataFrame has {n_rows} rows; expected at most {schema.max_rows}."
                ),
                context={"actual": n_rows, "maximum": schema.max_rows},
            )
        )

    # --- Column presence and dtype checks ---
    actual_cols = set(df.columns)
    for col_spec in schema.columns:
        if col_spec.name not in actual_cols:
            issues.append(
                ProviderIssue(
                    code="DRIFT_MISSING_COLUMN",
                    severity="error",
                    provider=provider,
                    capability=dataset_type,
                    message=f"Expected column {col_spec.name!r} not found in DataFrame.",
                    context={
                        "column": col_spec.name,
                        "actual_columns": sorted(actual_cols),
                    },
                )
            )
            continue

        series = df[col_spec.name]
        actual_dtype = str(series.dtype)
        expected_prefix = col_spec.dtype
        if not _dtype_matches(series, expected_prefix):
            severity = "warning" if col_spec.nullable else "error"
            issues.append(
                ProviderIssue(
                    code="DRIFT_DTYPE_MISMATCH",
                    severity=severity,
                    provider=provider,
                    capability=dataset_type,
                    message=(
                        f"Column {col_spec.name!r} has dtype {actual_dtype!r}; "
                        f"expected {expected_prefix!r}."
                    ),
                    context={
                        "column": col_spec.name,
                        "actual_dtype": actual_dtype,
                        "expected_dtype": expected_prefix,
                    },
                )
            )

        # null check for non-nullable columns
        if not col_spec.nullable and series.isna().any():
            n_null = int(series.isna().sum())
            issues.append(
                ProviderIssue(
                    code="DRIFT_UNEXPECTED_NULLS",
                    severity="warning",
                    provider=provider,
                    capability=dataset_type,
                    message=(
                        f"Column {col_spec.name!r} has {n_null} null "
                        f"values but is expected non-nullable."
                    ),
                    context={"column": col_spec.name, "null_count": n_null},
                )
            )

    return issues


def get_baseline_schema(provider: str, dataset_type: str) -> DatasetSchema | None:
    """Return the built-in baseline schema for the given provider/dataset, or None."""
    return _get_baseline().get((provider.lower(), dataset_type))


def register_schema(schema: DatasetSchema) -> None:
    """Register or overwrite a baseline schema (useful for custom providers)."""
    baseline = _get_baseline()
    baseline[(schema.provider.lower(), schema.dataset_type)] = schema
