"""Relative strength vs benchmark."""

from __future__ import annotations

import pandas as pd


def compute_relative_strength(
    symbol_close: pd.Series,
    benchmark_close: pd.Series,
    period: int,
) -> pd.Series:
    """Compute relative strength: symbol_return / benchmark_return over period.

    RS > 0: symbol outperforms benchmark
    RS < 0: symbol underperforms benchmark
    """
    sym_return = symbol_close / symbol_close.shift(period) - 1
    bench_return = benchmark_close / benchmark_close.shift(period) - 1
    return sym_return - bench_return


def compute_relative_strength_features(
    df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute RS features for a symbol vs benchmark.

    Args:
        df: symbol OHLCV DataFrame with DatetimeIndex
        benchmark_df: benchmark OHLCV DataFrame with DatetimeIndex

    Returns:
        df with rs_20d_vs_vnindex and rs_60d_vs_vnindex added.
    """
    df = df.copy()
    # Align benchmark to symbol's dates
    bench_close = benchmark_df["close"].reindex(df.index)
    df["rs_20d_vs_vnindex"] = compute_relative_strength(df["close"], bench_close, 20)
    df["rs_60d_vs_vnindex"] = compute_relative_strength(df["close"], bench_close, 60)
    return df
