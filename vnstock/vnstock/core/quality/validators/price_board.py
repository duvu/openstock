"""Price board snapshot validator.

Validates DataFrames representing live price board data against the
standard price board contract defined in the data quality design.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnstock.core.quality.base import BaseValidator
from vnstock.core.quality.models import QualityIssue, ValidationReport
from vnstock.core.quality.rules import freshness as freshness_rules
from vnstock.core.quality.rules import schema as schema_rules

_REQUIRED_COLUMNS = ["symbol", "reference_price", "close_price", "volume_accumulated"]
_OPTIONAL_PRICE_COLUMNS = [
    "ceiling_price",
    "floor_price",
    "open_price",
    "high_price",
    "low_price",
    "reference_price",
    "close_price",
    "bid_price_1",
    "ask_price_1",
]
_OPTIONAL_VOLUME_COLUMNS = [
    "volume_accumulated",
    "bid_vol_1",
    "ask_vol_1",
    "foreign_buy_volume",
    "foreign_sell_volume",
]


def _safe_positional_index(df, label_index):
    """Return 0-based positional index for label_index; avoids int() crash on non-int indices."""
    try:
        loc = df.index.get_loc(label_index)
        if isinstance(loc, int):
            return loc
        # Duplicate labels: get_loc returns slice or boolean ndarray
        if isinstance(loc, slice):
            # Return the start of the slice (first matching position)
            return loc.start if loc.start is not None else 0
        # Boolean ndarray
        if hasattr(loc, "nonzero"):
            nz = loc.nonzero()[0]
            return int(nz[0]) if len(nz) > 0 else None
        return None
    except Exception:
        try:
            return int(label_index)
        except (TypeError, ValueError):
            return None


class PriceBoardValidator(BaseValidator):
    """Validate price board snapshot DataFrames.

    Checks performed (in order):

    1. Schema — required columns, empty DataFrame.
    2. Duplicate symbols.
    3. Floor / reference / ceiling price consistency.
    4. Close price within floor and ceiling.
    5. Bid / ask crossing.
    6. Non-negative volume fields.
    7. Freshness metadata (when available).
    """

    dataset_type: str = "price_board"

    def validate(
        self,
        df: pd.DataFrame,
        provider: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        config: Any | None = None,
    ) -> ValidationReport:
        from vnstock.core.settings import QualityConfig

        cfg: QualityConfig = config if config is not None else QualityConfig()
        max_ex = cfg.max_error_examples

        errors: list[QualityIssue] = []
        warnings: list[QualityIssue] = []
        infos: list[QualityIssue] = []

        def _classify(issues: list[QualityIssue]) -> None:
            for iss in issues:
                if iss.severity == "error":
                    errors.append(iss)
                elif iss.severity == "warning":
                    warnings.append(iss)
                else:
                    infos.append(iss)

        # 1. Schema
        _classify(schema_rules.check_required_columns(df, _REQUIRED_COLUMNS))
        _classify(schema_rules.check_empty_dataframe(df))

        if not df.empty:
            # 2. Duplicate symbols
            _classify(_check_duplicate_symbols(df, max_ex))

            # 3. Floor / reference / ceiling consistency
            _classify(_check_price_band_consistency(df, max_ex))

            # 4. Bid / ask crossing
            _classify(_check_bid_ask_crossed(df, max_ex))

            # 5. Non-negative volumes
            _classify(_check_non_negative_volumes(df, max_ex))

        # 6. Freshness
        _classify(
            freshness_rules.check_stale_price_board(df, cfg.stale_price_board_seconds)
        )

        return ValidationReport(
            valid=len(errors) == 0,
            dataset_type=self.dataset_type,
            provider=provider,
            symbol=symbol,
            interval=interval,
            row_count=len(df),
            latest_time=None,
            freshness_status="unknown",
            errors=errors,
            warnings=warnings,
            infos=infos,
        )


def _check_duplicate_symbols(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    if "symbol" not in df.columns:
        return []
    issues: list[QualityIssue] = []
    dup_mask = df["symbol"].duplicated(keep="first")
    for idx in df.index[dup_mask][:max_examples]:
        issues.append(
            QualityIssue(
                code="BOARD_DUPLICATE_SYMBOL",
                severity="warning",
                message=f"Symbol '{df.at[idx, 'symbol']}' appears more than once at row {idx}.",
                column="symbol",
                row_index=_safe_positional_index(df, idx),
                value=str(df.at[idx, "symbol"]),
            )
        )
    return issues


def _check_price_band_consistency(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    """Check floor <= reference <= ceiling and floor <= close <= ceiling."""
    issues: list[QualityIssue] = []
    has_floor = "floor_price" in df.columns
    has_ref = "reference_price" in df.columns
    has_ceil = "ceiling_price" in df.columns
    has_close = "close_price" in df.columns

    if not (has_floor and has_ceil):
        return issues

    floor = pd.to_numeric(df["floor_price"], errors="coerce")
    ceil = pd.to_numeric(df["ceiling_price"], errors="coerce")

    # floor > ceiling is itself invalid
    band_invalid = (floor > ceil) & floor.notna() & ceil.notna()
    for idx in df.index[band_invalid][:max_examples]:
        issues.append(
            QualityIssue(
                code="BOARD_PRICE_OUTSIDE_FLOOR_CEILING",
                severity="error",
                message=f"floor_price > ceiling_price at row {idx}.",
                row_index=_safe_positional_index(df, idx),
                context={
                    "floor_price": df.at[idx, "floor_price"],
                    "ceiling_price": df.at[idx, "ceiling_price"],
                },
            )
        )
        if len(issues) >= max_examples:
            return issues

    # reference out of band
    if has_ref:
        ref = pd.to_numeric(df["reference_price"], errors="coerce")
        out_band = (
            ((ref < floor) | (ref > ceil)) & ref.notna() & floor.notna() & ceil.notna()
        )
        for idx in df.index[out_band][:max_examples]:
            issues.append(
                QualityIssue(
                    code="BOARD_MISSING_REFERENCE_PRICE",
                    severity="warning",
                    message=f"reference_price is outside [floor, ceiling] at row {idx}.",
                    column="reference_price",
                    row_index=_safe_positional_index(df, idx),
                )
            )
            if len(issues) >= max_examples:
                return issues

    # close out of band
    if has_close:
        close = pd.to_numeric(df["close_price"], errors="coerce")
        out_band = (
            ((close < floor) | (close > ceil))
            & close.notna()
            & floor.notna()
            & ceil.notna()
        )
        for idx in df.index[out_band][:max_examples]:
            issues.append(
                QualityIssue(
                    code="BOARD_PRICE_OUTSIDE_FLOOR_CEILING",
                    severity="error",
                    message=f"close_price is outside [floor, ceiling] at row {idx}.",
                    column="close_price",
                    row_index=_safe_positional_index(df, idx),
                    value=df.at[idx, "close_price"],
                )
            )
            if len(issues) >= max_examples:
                return issues

    return issues


def _check_bid_ask_crossed(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    """Best bid should be <= best ask when both are non-zero."""
    issues: list[QualityIssue] = []
    if "bid_price_1" not in df.columns or "ask_price_1" not in df.columns:
        return issues

    bid = pd.to_numeric(df["bid_price_1"], errors="coerce")
    ask = pd.to_numeric(df["ask_price_1"], errors="coerce")
    # Only check when both are non-zero and non-null
    valid = bid.notna() & ask.notna() & (bid > 0) & (ask > 0)
    crossed = valid & (bid > ask)

    for idx in df.index[crossed][:max_examples]:
        issues.append(
            QualityIssue(
                code="BOARD_BID_ASK_CROSSED",
                severity="warning",
                message=f"Best bid > best ask at row {idx}.",
                row_index=_safe_positional_index(df, idx),
                context={
                    "bid_price_1": df.at[idx, "bid_price_1"],
                    "ask_price_1": df.at[idx, "ask_price_1"],
                },
            )
        )
    return issues


def _check_non_negative_volumes(
    df: pd.DataFrame, max_examples: int = 20
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    present_volume_cols = [c for c in _OPTIONAL_VOLUME_COLUMNS if c in df.columns]
    for col in present_volume_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        neg_mask = series < 0
        for idx in df.index[neg_mask][:max_examples]:
            code = (
                "BOARD_NEGATIVE_BID_VOLUME"
                if "bid" in col
                else "BOARD_NEGATIVE_ASK_VOLUME"
                if "ask" in col
                else "NUMERIC_NEGATIVE_VOLUME"
            )
            issues.append(
                QualityIssue(
                    code=code,
                    severity="error",
                    message=f"Column '{col}' has a negative volume at row {idx}.",
                    column=col,
                    row_index=_safe_positional_index(df, idx),
                    value=df.at[idx, col],
                )
            )
            if len(issues) >= max_examples:
                return issues
    return issues
