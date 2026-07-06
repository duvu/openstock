"""
Unit tests for health-aware PluginRouter (Phase 3 behavior).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.provider.exceptions import (
    NoHealthyProviderError,
    ProviderDisabledError,
    ProviderInCooldownError,
    UnsupportedDatasetError,
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.health import (
    HealthStatus,
    InMemoryProviderHealthStore,
    ProviderHealth,
)
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter
from vnstock.core.provider.routing import RoutingDecision, RoutingPolicy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_router(
    plugins: list,
    policy: RoutingPolicy | None = None,
    priority: list[str] | None = None,
) -> tuple[PluginRouter, InMemoryProviderHealthStore]:
    registry = PluginRegistry()
    for p in plugins:
        registry.register(p)
    store = InMemoryProviderHealthStore()
    router = PluginRouter(
        registry, default_priority=priority, health_store=store, policy=policy
    )
    return router, store


# ---------------------------------------------------------------------------
# Auto routing — health-aware selection
# ---------------------------------------------------------------------------


class TestAutoRouting:
    def test_selects_healthy_provider(self):
        kbs = FakeProviderPlugin("KBS")
        vci = FakeProviderPlugin("VCI")
        router, store = make_router([kbs, vci], priority=["KBS", "VCI"])
        store.record_success("KBS", "equity.ohlcv")
        store.record_failure("VCI", "equity.ohlcv")

        selected = router.resolve("equity.ohlcv")
        assert selected.name == "KBS"

    def test_falls_back_to_degraded_when_no_healthy(self):
        kbs = FakeProviderPlugin("KBS")
        vci = FakeProviderPlugin("VCI")
        router, store = make_router([kbs, vci], priority=["KBS", "VCI"])
        store.record_failure("KBS", "equity.ohlcv")  # degraded
        store.record_failure("VCI", "equity.ohlcv")  # degraded

        selected = router.resolve("equity.ohlcv")
        # KBS is first in priority, both are DEGRADED → KBS selected as fallback
        assert selected.name == "KBS"
        assert router.last_decision.fallback is True

    def test_rejects_failing_provider_by_default(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        now = datetime.now(tz=timezone.utc)
        for _ in range(3):
            store.record_failure("KBS", "equity.ohlcv", failure_threshold=3, now=now)

        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")

    def test_allows_failing_with_permissive_policy(self):
        kbs = FakeProviderPlugin("KBS")
        policy = RoutingPolicy.permissive()
        router, store = make_router([kbs], policy=policy)
        # Use far-past time so cooldown already expired
        far_past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
        for _ in range(3):
            store.record_failure(
                "KBS",
                "equity.ohlcv",
                failure_threshold=3,
                cooldown_seconds=60,
                now=far_past,
            )

        selected = router.resolve("equity.ohlcv")
        assert selected.name == "KBS"

    def test_skips_cooled_down_provider(self):
        kbs = FakeProviderPlugin("KBS")
        vci = FakeProviderPlugin("VCI")
        router, store = make_router([kbs, vci], priority=["KBS", "VCI"])
        # Put KBS in cooldown
        now = datetime.now(tz=timezone.utc)
        for _ in range(3):
            store.record_failure(
                "KBS",
                "equity.ohlcv",
                failure_threshold=3,
                cooldown_seconds=600,
                now=now,
            )

        store.record_success("VCI", "equity.ohlcv")

        selected = router.resolve("equity.ohlcv")
        assert selected.name == "VCI"

    def test_raises_when_no_candidates(self):
        kbs = FakeProviderPlugin("KBS", supported_datasets=["equity.quote"])
        router, _ = make_router([kbs])
        with pytest.raises(UnsupportedDatasetError):
            router.resolve("equity.ohlcv")

    def test_raises_no_healthy_when_all_disabled(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", status=HealthStatus.DISABLED
        )
        store.set(h)
        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")


# ---------------------------------------------------------------------------
# Explicit routing
# ---------------------------------------------------------------------------


class TestExplicitRouting:
    def test_explicit_source_succeeds(self):
        kbs = FakeProviderPlugin("KBS")
        router, _ = make_router([kbs])
        selected = router.resolve("equity.ohlcv", source="KBS")
        assert selected.name == "KBS"

    def test_explicit_source_degraded_warns_but_succeeds(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        store.record_failure("KBS", "equity.ohlcv")

        selected = router.resolve("equity.ohlcv", source="KBS")
        assert selected.name == "KBS"
        assert router.last_decision.warnings

    def test_explicit_source_failing_warns_but_succeeds(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        now = datetime.now(tz=timezone.utc)
        # Drive to FAILING but avoid active cooldown (use expired cooldown window)
        far_past = now - timedelta(hours=1)
        for _ in range(3):
            store.record_failure(
                "KBS",
                "equity.ohlcv",
                failure_threshold=3,
                cooldown_seconds=1,
                now=far_past,
            )

        selected = router.resolve("equity.ohlcv", source="KBS")
        assert selected.name == "KBS"
        assert any("FAILING" in w for w in router.last_decision.warnings)

    def test_explicit_source_in_cooldown_raises(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        now = datetime.now(tz=timezone.utc)
        for _ in range(3):
            store.record_failure(
                "KBS",
                "equity.ohlcv",
                failure_threshold=3,
                cooldown_seconds=600,
                now=now,
            )

        with pytest.raises(ProviderInCooldownError):
            router.resolve("equity.ohlcv", source="KBS")

    def test_explicit_source_disabled_raises(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", status=HealthStatus.DISABLED
        )
        store.set(h)

        with pytest.raises(ProviderDisabledError):
            router.resolve("equity.ohlcv", source="KBS")

    def test_explicit_unsupported_dataset_raises(self):
        kbs = FakeProviderPlugin("KBS", supported_datasets=["equity.quote"])
        router, _ = make_router([kbs])
        with pytest.raises(UnsupportedDatasetForProviderError):
            router.resolve("equity.ohlcv", source="KBS")


# ---------------------------------------------------------------------------
# Routing decision diagnostics
# ---------------------------------------------------------------------------


class TestRoutingDecision:
    def test_decision_is_routing_decision_instance(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        store.record_success("KBS", "equity.ohlcv")
        router.resolve("equity.ohlcv")
        assert isinstance(router.last_decision, RoutingDecision)

    def test_last_diagnostics_is_dict(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        store.record_success("KBS", "equity.ohlcv")
        router.resolve("equity.ohlcv")
        d = router.last_diagnostics
        assert isinstance(d, dict)
        assert "selected_provider" in d
        assert "dataset" in d

    def test_decision_to_dict_no_secrets(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        store.record_success("KBS", "equity.ohlcv")
        router.resolve("equity.ohlcv")
        d = router.last_decision.to_dict()
        forbidden = {"password", "api_key", "access_token", "authorization"}
        # Flatten all string values and check
        all_keys = set(d.keys())
        assert not forbidden & all_keys

    def test_rejected_providers_in_decision(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", status=HealthStatus.DISABLED
        )
        store.set(h)
        with pytest.raises(NoHealthyProviderError):
            router.resolve("equity.ohlcv")
        assert "KBS" in router.last_decision.rejected

    def test_health_snapshot_in_decision(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        store.record_success("KBS", "equity.ohlcv")
        router.resolve("equity.ohlcv")
        snapshot = router.last_decision.health_snapshot
        assert "KBS" in snapshot
        assert snapshot["KBS"]["status"] == "HEALTHY"


# ---------------------------------------------------------------------------
# Record success / failure on router
# ---------------------------------------------------------------------------


class TestRouterRecording:
    def test_record_success_updates_health(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        router.record_success("KBS", "equity.ohlcv", latency_ms=100.0)
        h = store.get("KBS", "equity.ohlcv")
        assert h.status == HealthStatus.HEALTHY
        assert h.latency_ms == 100.0

    def test_record_failure_updates_health(self):
        kbs = FakeProviderPlugin("KBS")
        router, store = make_router([kbs])
        router.record_failure("KBS", "equity.ohlcv", notes="timeout")
        h = store.get("KBS", "equity.ohlcv")
        assert h.failure_count == 1


# ---------------------------------------------------------------------------
# RoutingPolicy
# ---------------------------------------------------------------------------


class TestRoutingPolicy:
    def test_default_policy_values(self):
        p = RoutingPolicy.default()
        assert p.prefer_healthy is True
        assert p.allow_degraded is True
        assert p.allow_failing_fallback is False
        assert p.respect_cooldown is True
        assert p.use_priority_tiebreaker is True

    def test_strict_policy_no_degraded(self):
        p = RoutingPolicy.strict()
        assert p.allow_degraded is False

    def test_permissive_policy_allows_failing(self):
        p = RoutingPolicy.permissive()
        assert p.allow_failing_fallback is True
