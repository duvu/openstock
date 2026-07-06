"""
Provider health model, health store interface, and in-memory implementation.

This module tracks runtime health state per (provider, dataset) pair and
exposes an interface for recording successes and failures, managing cooldowns,
and querying health for routing decisions.

Health status semantics
-----------------------

HEALTHY
    The provider has been responding correctly to requests for this dataset.
    It is selected first by the health-aware router.

DEGRADED
    The provider is returning data but with elevated error rate, schema drift,
    or unusual latency. May still be selected as a fallback when no HEALTHY
    provider is available, depending on routing policy.

FAILING
    The provider is consistently returning errors for this dataset. Excluded
    from auto routing by default (allow_failing_fallback=False in policy).

UNKNOWN
    No health data has been recorded yet for this (provider, dataset) pair.
    Treated conservatively — eligible for auto routing on first attempt but
    transitions quickly once data is observed.

DISABLED
    Administratively disabled. Never selected by the router regardless of
    policy settings.

Cooldown behavior
-----------------

When ``record_failure`` is called and the failure count exceeds
``failure_threshold``, the provider enters a cooldown period. While in
cooldown, the router skips this provider for auto routing (when
``respect_cooldown=True`` in policy). Cooldown expires automatically based
on ``cooldown_seconds``. Calling ``record_success`` resets the failure
count and clears any active cooldown.

Usage::

    from vnstock.core.provider.health import InMemoryProviderHealthStore

    store = InMemoryProviderHealthStore()

    # Record outcomes
    store.record_success("KBS", "equity.ohlcv", latency_ms=120.0)
    store.record_failure("VCI", "equity.ohlcv")

    # Query
    health = store.get("KBS", "equity.ohlcv")
    print(health.status)   # HealthStatus.HEALTHY

    # List all tracked (provider, dataset) pairs for a dataset
    entries = store.list_for_dataset("equity.ohlcv")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    """Health status values for a (provider, dataset) pair.

    These are strings so they serialize cleanly in diagnostics dicts and
    ``DataFrame.attrs``.
    """

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILING = "FAILING"
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"


@dataclass
class ProviderHealth:
    """Health snapshot for a single (provider, dataset) pair.

    Attributes:
        provider: Provider name (e.g. ``"KBS"``).
        dataset: Dotted dataset name (e.g. ``"equity.ohlcv"``).
        status: Current :class:`HealthStatus`.
        latency_ms: Most recently recorded fetch latency in milliseconds, or
            ``None`` if unknown.
        freshness_score: Data freshness metric in ``[0.0, 1.0]`` where ``1.0``
            means perfectly fresh.  ``None`` if not computed.
        last_success_at: UTC timestamp of the most recent successful fetch.
        last_failure_at: UTC timestamp of the most recent failed fetch.
        failure_count: Number of consecutive failures since the last success.
        success_count: Total recorded successes (not reset on failure).
        cooldown_until: UTC timestamp until which this provider is in
            cooldown. ``None`` means no active cooldown.
        notes: Free-form diagnostic text for human inspection.
    """

    provider: str
    dataset: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float | None = None
    freshness_score: float | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int = 0
    success_count: int = 0
    cooldown_until: datetime | None = None
    notes: str | None = None

    def is_in_cooldown(self, now: datetime | None = None) -> bool:
        """Return ``True`` if the cooldown window is currently active.

        Args:
            now: Override the current UTC time (useful for testing).
        """
        if self.cooldown_until is None:
            return False
        _now = now or datetime.now(tz=timezone.utc)
        return _now < self.cooldown_until

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for diagnostics embedding."""
        return {
            "provider": self.provider,
            "dataset": self.dataset,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "freshness_score": self.freshness_score,
            "last_success_at": self.last_success_at.isoformat()
            if self.last_success_at
            else None,
            "last_failure_at": self.last_failure_at.isoformat()
            if self.last_failure_at
            else None,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "cooldown_until": self.cooldown_until.isoformat()
            if self.cooldown_until
            else None,
            "notes": self.notes,
        }


class ProviderHealthStore(ABC):
    """Abstract interface for a provider health data store."""

    @abstractmethod
    def get(self, provider: str, dataset: str) -> ProviderHealth:
        """Return health for *(provider, dataset)*, defaulting to UNKNOWN."""
        ...

    @abstractmethod
    def set(self, health: ProviderHealth) -> None:
        """Persist a :class:`ProviderHealth` record."""
        ...

    @abstractmethod
    def record_success(
        self,
        provider: str,
        dataset: str,
        latency_ms: float | None = None,
        freshness_score: float | None = None,
        now: datetime | None = None,
    ) -> ProviderHealth:
        """Update health after a successful fetch.

        Resets failure count and clears any active cooldown.

        Returns:
            The updated :class:`ProviderHealth` record.
        """
        ...

    @abstractmethod
    def record_failure(
        self,
        provider: str,
        dataset: str,
        notes: str | None = None,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        now: datetime | None = None,
    ) -> ProviderHealth:
        """Update health after a fetch failure.

        Increments failure count. When failure count reaches or exceeds
        *failure_threshold*, transitions status to FAILING and sets a
        cooldown window.

        Returns:
            The updated :class:`ProviderHealth` record.
        """
        ...

    @abstractmethod
    def list_for_dataset(self, dataset: str) -> list[ProviderHealth]:
        """Return all tracked health records for *dataset*."""
        ...


class InMemoryProviderHealthStore(ProviderHealthStore):
    """Thread-unsafe in-process health store backed by a plain dict.

    This is the default implementation. It is intentionally simple: no
    persistence, no locking, no TTL eviction. Suitable for single-process
    scripts and tests.

    Args:
        failure_threshold: Default consecutive-failure threshold before
            entering FAILING status and cooldown.  Can be overridden per
            ``record_failure`` call.
        cooldown_seconds: Default cooldown window in seconds.  Can be
            overridden per ``record_failure`` call.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._default_failure_threshold = failure_threshold
        self._default_cooldown_seconds = cooldown_seconds
        # Keyed by (provider_upper, dataset)
        self._store: dict[tuple[str, str], ProviderHealth] = {}

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get(self, provider: str, dataset: str) -> ProviderHealth:
        """Return health for *(provider, dataset)*, defaulting to UNKNOWN."""
        key = (provider.upper(), dataset)
        if key not in self._store:
            return ProviderHealth(provider=provider.upper(), dataset=dataset)
        return self._store[key]

    def set(self, health: ProviderHealth) -> None:
        """Persist a :class:`ProviderHealth` record."""
        key = (health.provider.upper(), health.dataset)
        self._store[key] = health

    def record_success(
        self,
        provider: str,
        dataset: str,
        latency_ms: float | None = None,
        freshness_score: float | None = None,
        now: datetime | None = None,
    ) -> ProviderHealth:
        """Record a successful fetch. Resets failure count and cooldown."""
        _now = now or datetime.now(tz=timezone.utc)
        health = self.get(provider, dataset)

        health.provider = provider.upper()
        health.dataset = dataset
        health.status = HealthStatus.HEALTHY
        health.last_success_at = _now
        health.failure_count = 0
        health.cooldown_until = None
        health.success_count += 1

        if latency_ms is not None:
            health.latency_ms = latency_ms
        if freshness_score is not None:
            health.freshness_score = freshness_score

        self.set(health)
        return health

    def record_failure(
        self,
        provider: str,
        dataset: str,
        notes: str | None = None,
        failure_threshold: int | None = None,
        cooldown_seconds: float | None = None,
        now: datetime | None = None,
    ) -> ProviderHealth:
        """Record a fetch failure. Enters cooldown when threshold is reached.

        Args:
            provider: Provider name.
            dataset: Dataset name.
            notes: Optional human-readable failure notes.
            failure_threshold: Consecutive failures before FAILING + cooldown.
                Defaults to instance-level default.
            cooldown_seconds: Cooldown window after threshold is reached.
                Defaults to instance-level default.
            now: Override for current UTC time (testing).
        """
        _threshold = (
            failure_threshold
            if failure_threshold is not None
            else self._default_failure_threshold
        )
        _cooldown = (
            cooldown_seconds
            if cooldown_seconds is not None
            else self._default_cooldown_seconds
        )
        _now = now or datetime.now(tz=timezone.utc)

        health = self.get(provider, dataset)
        health.provider = provider.upper()
        health.dataset = dataset
        health.last_failure_at = _now
        health.failure_count += 1

        if notes:
            health.notes = notes

        if health.failure_count >= _threshold:
            health.status = HealthStatus.FAILING
            from datetime import timedelta

            health.cooldown_until = _now + timedelta(seconds=_cooldown)
        elif health.failure_count == 1 and health.status == HealthStatus.HEALTHY:
            # Single failure after a healthy streak → DEGRADED (not yet FAILING)
            health.status = HealthStatus.DEGRADED
        elif health.status == HealthStatus.UNKNOWN:
            # First-ever failure
            health.status = HealthStatus.DEGRADED

        self.set(health)
        return health

    def list_for_dataset(self, dataset: str) -> list[ProviderHealth]:
        """Return all tracked health records for *dataset*."""
        return [h for (_, ds), h in self._store.items() if ds == dataset]

    # ------------------------------------------------------------------ #
    # Inspection helpers                                                   #
    # ------------------------------------------------------------------ #

    def all_providers(self) -> list[str]:
        """Return unique provider names in the store."""
        return list({p for (p, _) in self._store})

    def all_datasets(self) -> list[str]:
        """Return unique dataset names in the store."""
        return list({ds for (_, ds) in self._store})

    def clear(self) -> None:
        """Remove all stored health records."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:  # pragma: no cover
        return f"InMemoryProviderHealthStore(entries={len(self._store)})"


# ---------------------------------------------------------------------------
# Module-level default shared store
# ---------------------------------------------------------------------------

#: Default shared health store used by ``PluginRouter`` unless overridden.
DEFAULT_HEALTH_STORE: InMemoryProviderHealthStore = InMemoryProviderHealthStore()
