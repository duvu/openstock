"""Executable legacy CLI remediation plans for deep-analysis inputs."""

from __future__ import annotations

from shlex import quote

from vnalpha.data_availability.deep_readiness_models import (
    RemediationAction,
    RemediationStep,
)
from vnalpha.data_availability.policy import DEFAULT_POLICY


def remediation_steps(
    artifact: str, symbol: str, resolved_date: str, lookback_start: str
) -> tuple[RemediationStep, ...]:
    safe_symbol = quote(symbol)
    steps = {
        "symbol_master": (_symbols_step(artifact),),
        "canonical_ohlcv": _canonical_steps(
            artifact, safe_symbol, lookback_start, resolved_date
        ),
        "benchmark_ohlcv": _benchmark_steps(artifact, lookback_start, resolved_date),
        "feature_snapshot": (_features_step(artifact, safe_symbol, resolved_date),),
        "candidate_score": (_score_step(artifact, safe_symbol, resolved_date),),
    }
    return steps.get(artifact, ())


def _symbols_step(artifact: str) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.SYNC_SYMBOLS,
        artifact=artifact,
        command_surface="cli",
        command="vnalpha sync symbols",
        description="Refresh the persisted symbol master.",
        required=True,
    )


def _canonical_steps(
    artifact: str, symbol: str, lookback_start: str, resolved_date: str
) -> tuple[RemediationStep, RemediationStep]:
    return (
        RemediationStep(
            action=RemediationAction.SYNC_OHLCV,
            artifact=artifact,
            command_surface="cli",
            command=(
                "vnalpha sync ohlcv "
                f"--symbols {symbol} --start {lookback_start} --end {resolved_date}"
            ),
            description="Download the required symbol OHLCV window.",
            required=True,
        ),
        RemediationStep(
            action=RemediationAction.BUILD_CANONICAL,
            artifact=artifact,
            command_surface="cli",
            command=f"vnalpha build canonical --symbol {symbol}",
            description="Build canonical OHLCV from downloaded bars.",
            required=True,
        ),
    )


def _benchmark_steps(
    artifact: str, lookback_start: str, resolved_date: str
) -> tuple[RemediationStep, RemediationStep]:
    benchmark = DEFAULT_POLICY.benchmark
    return (
        RemediationStep(
            action=RemediationAction.SYNC_BENCHMARK,
            artifact=artifact,
            command_surface="cli",
            command=(
                "vnalpha sync index "
                f"--symbol {benchmark} --start {lookback_start} --end {resolved_date}"
            ),
            description="Download the required benchmark OHLCV window.",
            required=True,
        ),
        RemediationStep(
            action=RemediationAction.BUILD_CANONICAL,
            artifact=artifact,
            command_surface="cli",
            command=f"vnalpha build canonical --symbol {benchmark}",
            description="Build canonical OHLCV for the benchmark.",
            required=True,
        ),
    )


def _features_step(artifact: str, symbol: str, resolved_date: str) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.BUILD_FEATURES,
        artifact=artifact,
        command_surface="cli",
        command=f"vnalpha build features --symbols {symbol} --date {resolved_date}",
        description="Build the symbol feature snapshot.",
        required=True,
    )


def _score_step(artifact: str, symbol: str, resolved_date: str) -> RemediationStep:
    return RemediationStep(
        action=RemediationAction.SCORE_SYMBOL,
        artifact=artifact,
        command_surface="cli",
        command=f"vnalpha score --symbols {symbol} --date {resolved_date}",
        description="Generate the symbol candidate score.",
        required=True,
    )
