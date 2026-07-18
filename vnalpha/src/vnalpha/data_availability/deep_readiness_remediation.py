"""Executable legacy CLI remediation plans for deep-analysis inputs."""

from __future__ import annotations

from dataclasses import dataclass
from shlex import quote

from vnalpha.data_availability.deep_readiness_models import (
    RemediationAction,
    RemediationStep,
)
from vnalpha.data_availability.models import EvidenceIssue
from vnalpha.data_availability.policy import DEFAULT_POLICY


@dataclass(frozen=True, slots=True)
class RemediationRequest:
    artifact: str
    symbol: str
    resolved_date: str
    lookback_start: str
    issues: tuple[EvidenceIssue, ...] = ()
    raw_window_ready: bool = False


def remediation_steps(request: RemediationRequest) -> tuple[RemediationStep, ...]:
    artifact = request.artifact
    safe_symbol = quote(request.symbol)
    steps = {
        "symbol_master": (_symbols_step(artifact),),
        "canonical_ohlcv": _canonical_steps(request, safe_symbol),
        "benchmark_ohlcv": _benchmark_steps(
            artifact, request.lookback_start, request.resolved_date
        ),
        "feature_snapshot": (
            _features_step(artifact, safe_symbol, request.resolved_date),
        ),
        "candidate_score": (_score_step(artifact, safe_symbol, request.resolved_date),),
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
    request: RemediationRequest, symbol: str
) -> tuple[RemediationStep, ...]:
    build = RemediationStep(
        action=RemediationAction.BUILD_CANONICAL,
        artifact=request.artifact,
        command_surface="cli",
        command=f"vnalpha build canonical --symbol {symbol}",
        description="Build and validate canonical OHLCV from persisted raw bars.",
        required=True,
    )
    if (
        request.raw_window_ready
        and EvidenceIssue.CANONICAL_GAPS_UNRESOLVED not in request.issues
    ):
        return (build,)
    return (
        RemediationStep(
            action=RemediationAction.SYNC_OHLCV,
            artifact=request.artifact,
            command_surface="cli",
            command=(
                "vnalpha sync ohlcv "
                f"--symbols {symbol} --start {request.lookback_start} "
                f"--end {request.resolved_date}"
            ),
            description="Download the required symbol OHLCV window.",
            required=True,
        ),
        build,
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
