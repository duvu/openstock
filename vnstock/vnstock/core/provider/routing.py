"""
Routing policy and routing decision models for health-aware provider selection.

These data structures are used by :class:`~vnstock.core.provider.plugin_router.PluginRouter`
to communicate routing behavior and results.

Usage::

    from vnstock.core.provider.routing import RoutingPolicy, RoutingDecision

    policy = RoutingPolicy(prefer_healthy=True, allow_degraded=True)
    # PluginRouter uses RoutingPolicy internally when resolving providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Default provider priority by dataset
# ---------------------------------------------------------------------------

#: Ordered list of provider names to prefer for each dataset during auto
#: routing.  Providers not listed are appended alphabetically.
DEFAULT_PROVIDER_PRIORITY: dict[str, list[str]] = {
    "equity.ohlcv": ["KBS", "VCI", "DNSE", "TCBS"],
    "index.ohlcv": ["KBS", "VCI", "DNSE"],
    "equity.quote": ["KBS", "VCI", "DNSE"],
    "equity.intraday_trades": ["KBS", "VCI"],
    "reference.symbols": ["KBS", "VCI"],
    "reference.company_info": ["KBS", "VCI"],
    "fundamental.balance_sheet": ["KBS", "VCI"],
    "fundamental.income_statement": ["KBS", "VCI"],
    "fundamental.cash_flow": ["KBS", "VCI"],
    "fundamental.financial_ratio": ["KBS", "VCI"],
    "fund.nav": ["FMARKET"],
}


@dataclass
class RoutingPolicy:
    """Configuration that governs health-aware provider selection.

    Attributes:
        prefer_healthy: When ``True``, HEALTHY providers are selected before
            DEGRADED providers during auto routing.
        allow_degraded: When ``True``, DEGRADED providers are eligible as a
            fallback when no HEALTHY provider is available.
        allow_failing_fallback: When ``True``, FAILING providers may be
            selected as a last resort (not recommended for production).
        respect_cooldown: When ``True``, providers that are currently in
            cooldown are skipped during auto routing.  Explicit ``source=``
            requests with a cooled-down provider raise
            :class:`~vnstock.core.provider.exceptions.ProviderInCooldownError`.
        use_priority_tiebreaker: When ``True``, the dataset-level priority
            list from :data:`DEFAULT_PROVIDER_PRIORITY` is used to break ties
            among providers with the same health status.
    """

    prefer_healthy: bool = True
    allow_degraded: bool = True
    allow_failing_fallback: bool = False
    respect_cooldown: bool = True
    use_priority_tiebreaker: bool = True

    @classmethod
    def default(cls) -> "RoutingPolicy":
        """Return the standard default policy."""
        return cls()

    @classmethod
    def permissive(cls) -> "RoutingPolicy":
        """Policy that allows all non-disabled providers including failing ones."""
        return cls(allow_failing_fallback=True)

    @classmethod
    def strict(cls) -> "RoutingPolicy":
        """Policy that only selects HEALTHY providers (no degraded fallback)."""
        return cls(allow_degraded=False)


@dataclass
class RoutingDecision:
    """Record of a single routing decision produced by :class:`PluginRouter`.

    Attributes:
        dataset: The dotted dataset name that was requested.
        requested_source: The ``source=`` value supplied by the caller.
            ``None`` or ``"auto"`` for automatic routing.
        selected_provider: Name of the provider that was selected.
            ``None`` if routing failed.
        candidates: All providers that support the dataset (pre-filter).
        rejected: Providers that were considered but rejected, with reasons.
        fallback: ``True`` if the selected provider is a fallback (e.g. a
            DEGRADED provider chosen because no HEALTHY one was available).
        reason: Human-readable explanation of why this provider was selected.
        health_snapshot: Dict of health summaries for each candidate, keyed
            by provider name.
        warnings: List of non-fatal warnings (e.g. selected provider is
            DEGRADED).
    """

    dataset: str
    requested_source: str | None = None
    selected_provider: str | None = None
    candidates: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    fallback: bool = False
    reason: str = ""
    health_snapshot: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for embedding in ``DataResult.diagnostics``."""
        return {
            "dataset": self.dataset,
            "requested_source": self.requested_source,
            "selected_provider": self.selected_provider,
            "candidates": self.candidates,
            "rejected": self.rejected,
            "fallback": self.fallback,
            "reason": self.reason,
            "health_snapshot": self.health_snapshot,
            "warnings": self.warnings,
        }
