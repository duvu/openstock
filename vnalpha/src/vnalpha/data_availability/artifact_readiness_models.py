"""Read-only, capability-scoped artifact readiness contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArtifactState(StrEnum):
    READY = "READY"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"


class ReadinessCapability(StrEnum):
    PRICE_ANALYSIS = "PRICE_ANALYSIS"
    CANDIDATE_RANKING = "CANDIDATE_RANKING"


class ReadinessAction(StrEnum):
    SYNC_SYMBOLS = "SYNC_SYMBOLS"
    SYNC_TARGET_OHLCV = "SYNC_TARGET_OHLCV"
    BUILD_TARGET_CANONICAL = "BUILD_TARGET_CANONICAL"
    SYNC_BENCHMARK_OHLCV = "SYNC_BENCHMARK_OHLCV"
    BUILD_BENCHMARK_CANONICAL = "BUILD_BENCHMARK_CANONICAL"
    BUILD_FEATURES = "BUILD_FEATURES"
    SCORE_SYMBOL = "SCORE_SYMBOL"


@dataclass(frozen=True, slots=True)
class BoundedDateRange:
    start_date: str
    end_date: str


@dataclass(frozen=True, slots=True)
class ReadinessActionProposal:
    action: ReadinessAction
    artifact: str
    dataset: str | None
    date_range: BoundedDateRange | None
    reason_code: str


@dataclass(frozen=True, slots=True)
class ArtifactReadiness:
    name: str
    state: ArtifactState
    required: bool
    repairable: bool
    reason_codes: tuple[str, ...]
    observed_date: str | None = None
    row_count: int | None = None
    actions: tuple[ReadinessActionProposal, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactReadinessRequest:
    symbol: str
    effective_date: str | None
    capability: ReadinessCapability
    historical: bool = False


@dataclass(frozen=True, slots=True)
class ArtifactReadinessReport:
    symbol: str
    requested_date: str | None
    effective_date: str
    requested_capability: ReadinessCapability
    fallback_capability: ReadinessCapability | None
    artifacts: tuple[ArtifactReadiness, ...]
    should_enqueue: bool

    @property
    def requested_ready(self) -> bool:
        return all(
            artifact.state is ArtifactState.READY
            for artifact in self.artifacts
            if artifact.required
        )

    @property
    def effective_capability(self) -> ReadinessCapability | None:
        if self.requested_ready:
            return self.requested_capability
        if self.fallback_capability is ReadinessCapability.PRICE_ANALYSIS:
            price_artifacts = self.artifacts[:2]
            if all(
                artifact.state is ArtifactState.READY for artifact in price_artifacts
            ):
                return self.fallback_capability
        return None
