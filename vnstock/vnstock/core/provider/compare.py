"""Cross-provider comparison for OHLCV and intraday datasets.

Aligns DataFrames from multiple providers on the time axis and computes
summary statistics on price/volume discrepancies. Returns a
ProviderComparisonReport with per-column diff summaries and issues.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnstock.core.provider.models import ProviderComparisonReport, ProviderIssue

# Thresholds for issue generation
_DEFAULT_PRICE_WARN_PCT = 0.01  # 1 % relative diff
_DEFAULT_PRICE_ERROR_PCT = 0.05  # 5 % relative diff
_DEFAULT_VOLUME_WARN_PCT = 0.10  # 10 % relative diff
_DEFAULT_COVERAGE_WARN_PCT = 0.20  # 20 % of dates missing from a provider


def _relative_diff(a: float, b: float) -> float:
    """Return |a - b| / max(|a|, |b|, 1e-9)."""
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom


def _diff_summary(series: pd.Series) -> dict[str, Any]:
    """Return basic stats dict for a numeric diff series (absolute values)."""
    if series.empty or series.isna().all():
        return {"count": 0, "mean": None, "max": None, "p95": None}
    s = series.dropna()
    return {
        "count": int(len(s)),
        "mean": float(s.mean()),
        "max": float(s.max()),
        "p95": float(s.quantile(0.95)),
    }


def compare_ohlcv(
    dataframes: dict[str, pd.DataFrame],
    *,
    symbol: str = "",
    interval: str = "",
    start: str = "",
    end: str = "",
    price_warn_pct: float = _DEFAULT_PRICE_WARN_PCT,
    price_error_pct: float = _DEFAULT_PRICE_ERROR_PCT,
    volume_warn_pct: float = _DEFAULT_VOLUME_WARN_PCT,
    coverage_warn_pct: float = _DEFAULT_COVERAGE_WARN_PCT,
) -> ProviderComparisonReport:
    """Compare OHLCV DataFrames from multiple providers.

    Parameters
    ----------
    dataframes:
        Mapping of provider name → normalized OHLCV DataFrame.
        Each DataFrame must have columns: time, open, high, low, close, volume.
    symbol:
        Symbol string (for report metadata only).
    interval, start, end:
        Metadata strings for the report.
    price_warn_pct / price_error_pct:
        Relative diff thresholds for price issue generation.
    volume_warn_pct:
        Relative diff threshold for volume issue generation.
    coverage_warn_pct:
        Fraction of dates missing from a provider that triggers a warning.

    Returns
    -------
    ProviderComparisonReport
    """
    providers = list(dataframes.keys()) if isinstance(dataframes, dict) else []

    # Guard: invalid input type
    if not isinstance(dataframes, dict):
        return ProviderComparisonReport(
            dataset_type="ohlcv",
            symbol=symbol,
            providers=[],
            comparable=False,
            base_provider="",
            interval=interval,
            start=start,
            end=end,
            issues=[
                ProviderIssue(
                    code="COMPARE_INVALID_INPUT",
                    severity="error",
                    provider="",
                    capability="ohlcv",
                    message=(
                        f"compare_ohlcv() requires a dict[str, DataFrame]; "
                        f"got {type(dataframes).__name__!r}."
                    ),
                )
            ],
        )

    # Guard: non-DataFrame values
    bad_providers = [
        k for k, v in dataframes.items() if not isinstance(v, pd.DataFrame)
    ]
    if bad_providers:
        return ProviderComparisonReport(
            dataset_type="ohlcv",
            symbol=symbol,
            providers=providers,
            comparable=False,
            base_provider=providers[0] if providers else "",
            interval=interval,
            start=start,
            end=end,
            issues=[
                ProviderIssue(
                    code="COMPARE_INVALID_INPUT",
                    severity="error",
                    provider=",".join(bad_providers),
                    capability="ohlcv",
                    message=(f"Providers {bad_providers} did not return a DataFrame."),
                )
            ],
        )

    if len(providers) < 2:
        return ProviderComparisonReport(
            dataset_type="ohlcv",
            symbol=symbol,
            providers=providers,
            comparable=False,
            base_provider=providers[0] if providers else "",
            interval=interval,
            start=start,
            end=end,
            issues=[
                ProviderIssue(
                    code="COMPARE_INSUFFICIENT_PROVIDERS",
                    severity="warning",
                    provider=",".join(providers),
                    capability="ohlcv",
                    message="Need at least 2 providers to compare.",
                )
            ],
        )

    # --- Align on time index ---
    base_name = providers[0]
    base_df = dataframes[base_name].copy()
    base_df["time"] = pd.to_datetime(base_df["time"])
    base_df = base_df.set_index("time").sort_index()

    row_count_by_provider: dict[str, int] = {base_name: len(base_df)}
    missing_dates_by_provider: dict[str, list[str]] = {}
    price_diff_summary: dict[str, Any] = {}
    volume_diff_summary: dict[str, Any] = {}
    issues: list[ProviderIssue] = []

    all_close_diffs: list[float] = []
    all_volume_diffs: list[float] = []

    for prov in providers[1:]:
        other_df = dataframes[prov].copy()
        other_df["time"] = pd.to_datetime(other_df["time"])
        other_df = other_df.set_index("time").sort_index()
        row_count_by_provider[prov] = len(other_df)

        # Find dates in base but not in other
        base_dates = set(base_df.index)
        other_dates = set(other_df.index)
        missing = sorted(str(d) for d in base_dates - other_dates)
        if missing:
            missing_dates_by_provider[prov] = missing
            missing_frac = len(missing) / max(len(base_dates), 1)
            if missing_frac >= coverage_warn_pct:
                issues.append(
                    ProviderIssue(
                        code="COMPARE_COVERAGE_GAP",
                        severity="warning",
                        provider=prov,
                        capability="ohlcv",
                        message=(
                            f"Provider {prov!r} is missing {len(missing)} "
                            f"dates ({missing_frac:.1%}) present in {base_name!r}."
                        ),
                        context={"missing_count": len(missing), "sample": missing[:5]},
                    )
                )

        # Compute close and volume diffs on common dates
        common_idx = base_df.index.intersection(other_df.index)
        if len(common_idx) == 0:
            issues.append(
                ProviderIssue(
                    code="COMPARE_NO_COMMON_DATES",
                    severity="error",
                    provider=prov,
                    capability="ohlcv",
                    message=f"No common dates between {base_name!r} and {prov!r}.",
                )
            )
            continue

        base_aligned = base_df.loc[common_idx]
        other_aligned = other_df.loc[common_idx]

        # Close price diff
        if "close" in base_aligned.columns and "close" in other_aligned.columns:
            close_diff = (
                base_aligned["close"] - other_aligned["close"]
            ).abs() / base_aligned["close"].abs().clip(lower=1e-9)
            all_close_diffs.extend(close_diff.tolist())
            max_close_diff = float(close_diff.max()) if not close_diff.empty else 0.0
            price_diff_summary[f"{base_name}_vs_{prov}"] = _diff_summary(close_diff)

            if max_close_diff >= price_error_pct:
                issues.append(
                    ProviderIssue(
                        code="COMPARE_PRICE_DIVERGENCE_HIGH",
                        severity="error",
                        provider=prov,
                        capability="ohlcv",
                        message=(
                            f"Max close price diff between {base_name!r} and {prov!r} "
                            f"is {max_close_diff:.2%} (threshold {price_error_pct:.2%})."
                        ),
                        context={"max_diff_pct": max_close_diff},
                    )
                )
            elif max_close_diff >= price_warn_pct:
                issues.append(
                    ProviderIssue(
                        code="COMPARE_PRICE_DIVERGENCE",
                        severity="warning",
                        provider=prov,
                        capability="ohlcv",
                        message=(
                            f"Max close price diff between {base_name!r} and {prov!r} "
                            f"is {max_close_diff:.2%} (threshold {price_warn_pct:.2%})."
                        ),
                        context={"max_diff_pct": max_close_diff},
                    )
                )

        # Volume diff
        if "volume" in base_aligned.columns and "volume" in other_aligned.columns:
            vol_diff = (
                base_aligned["volume"] - other_aligned["volume"]
            ).abs() / base_aligned["volume"].abs().clip(lower=1e-9)
            all_volume_diffs.extend(vol_diff.tolist())
            max_vol_diff = float(vol_diff.max()) if not vol_diff.empty else 0.0
            volume_diff_summary[f"{base_name}_vs_{prov}"] = _diff_summary(vol_diff)

            if max_vol_diff >= volume_warn_pct:
                issues.append(
                    ProviderIssue(
                        code="COMPARE_VOLUME_DIVERGENCE",
                        severity="warning",
                        provider=prov,
                        capability="ohlcv",
                        message=(
                            f"Max volume diff between {base_name!r} and {prov!r} "
                            f"is {max_vol_diff:.2%} (threshold {volume_warn_pct:.2%})."
                        ),
                        context={"max_diff_pct": max_vol_diff},
                    )
                )

    comparable = len(issues) == 0 or all(i.severity == "info" for i in issues)

    return ProviderComparisonReport(
        dataset_type="ohlcv",
        symbol=symbol,
        providers=providers,
        comparable=comparable,
        base_provider=base_name,
        row_count_by_provider=row_count_by_provider,
        missing_dates_by_provider=missing_dates_by_provider,
        price_diff_summary=price_diff_summary,
        volume_diff_summary=volume_diff_summary,
        issues=issues,
        interval=interval,
        start=start,
        end=end,
    )
