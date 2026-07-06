"""Router integration tests: ProviderRouter + capability registry + pools.

All tests are pure in-memory; no live provider calls.
"""

from __future__ import annotations

import time

import pytest

from vnstock.core.provider.capabilities import query_capabilities
from vnstock.core.router import ProviderRouter
from vnstock.ui._pools import POOLS, _build_pool_key


class TestProviderRouterBasic:
    """Core round-robin and cooldown logic."""

    def setup_method(self):
        self.router = ProviderRouter()

    def test_single_provider_always_returned(self):
        source = self.router.pick(("test", "ohlcv"), ["KBS"])
        assert source == "KBS"

    def test_round_robin_rotates(self):
        key = ("Market", "equity", "ohlcv")
        providers = ["KBS", "VCI", "DNSE"]
        picks = [self.router.pick(key, providers) for _ in range(6)]
        # Should cycle through all 3
        assert set(picks) == {"KBS", "VCI", "DNSE"}

    def test_empty_providers_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.router.pick(("test",), [])

    def test_failed_provider_enters_cooldown(self):
        key = ("test", "ohlcv")
        providers = ["KBS", "VCI"]
        self.router.mark_failed(key, "KBS", is_rate_limit=False)
        picks = [self.router.pick(key, providers) for _ in range(5)]
        # KBS is in cooldown, so VCI should be picked every time
        assert all(p == "VCI" for p in picks)

    def test_rate_limit_cooldown_longer(self):
        key = ("test", "ohlcv")
        self.router.mark_failed(key, "VCI", is_rate_limit=True)
        # Check that cooldown expiry is around RATE_LIMIT_COOLDOWN_SECS
        expiry = self.router._cooldowns.get((key, "VCI"), 0)
        now = time.time()
        remaining = expiry - now
        assert remaining > ProviderRouter.COOLDOWN_SECS, (
            f"Rate-limit cooldown {remaining:.1f}s should be > "
            f"normal {ProviderRouter.COOLDOWN_SECS}s"
        )

    def test_all_failed_returns_soonest_expiring(self):
        """When all providers are in cooldown, pick the one expiring first."""
        key = ("test", "ohlcv")
        providers = ["KBS", "VCI"]
        # KBS expires sooner
        self.router._cooldowns[(key, "KBS")] = time.time() + 10
        self.router._cooldowns[(key, "VCI")] = time.time() + 100
        chosen = self.router.pick(key, providers)
        assert chosen == "KBS"

    def test_reset_clears_state(self):
        key = ("test", "ohlcv")
        self.router.mark_failed(key, "KBS")
        self.router.reset()
        assert self.router._cooldowns == {}
        assert self.router._counters == {}


class TestProviderRouterDifferentPools:
    """Different pool keys maintain independent state."""

    def setup_method(self):
        self.router = ProviderRouter()

    def test_different_keys_independent_counters(self):
        key_a = ("Market", "equity", "ohlcv")
        key_b = ("Market", "equity", "intraday")
        providers = ["KBS", "VCI"]

        # Fail KBS on key_a only
        self.router.mark_failed(key_a, "KBS")
        pick_a = self.router.pick(key_a, providers)
        pick_b = self.router.pick(key_b, providers)

        # key_a should avoid KBS, key_b should still rotate normally
        assert pick_a == "VCI"
        # key_b first pick is KBS (not failed there)
        assert pick_b == "KBS"


class TestBuildPoolKey:
    """_build_pool_key helper builds correct tuples."""

    def test_flat_key_no_subdomain(self):
        key = _build_pool_key("equity_market", "ohlcv")
        assert key == ("equity_market", "ohlcv")

    def test_nested_key_with_subdomain(self):
        key = _build_pool_key("Market", "equity", consumed_subdomain="ohlcv")
        assert key == ("Market", "equity", "ohlcv")


class TestPoolsAlignWithCapabilities:
    """POOLS entries should correspond to registered capabilities."""

    def test_equity_ohlcv_pool_providers_have_capabilities(self):
        pool_providers = POOLS.get(("Market", "equity", "ohlcv"), [])
        assert len(pool_providers) >= 2, "equity ohlcv pool should have >= 2 providers"

        for provider in pool_providers:
            caps = query_capabilities(provider=provider.lower(), dataset_type="ohlcv")
            assert len(caps) > 0, (
                f"Provider {provider!r} is in equity ohlcv pool "
                "but has no OHLCV capability registered"
            )

    def test_equity_trades_pool_providers_have_capabilities(self):
        pool_providers = POOLS.get(("Market", "equity", "trades"), [])
        for provider in pool_providers:
            caps = query_capabilities(provider=provider.lower())
            assert len(caps) > 0, f"Pool provider {provider!r} has no capabilities"

    def test_futures_pool_uses_supported_providers(self):
        pool_providers = POOLS.get(("Market", "futures", "ohlcv"), [])
        # KBS and DNSE support futures
        assert "KBS" in pool_providers or "DNSE" in pool_providers

    def test_all_pool_providers_are_registered(self):
        """Every provider in every pool should appear in CAPABILITIES."""
        from vnstock.core.provider.capabilities import CAPABILITIES

        registered_providers = {c.provider.lower() for c in CAPABILITIES}
        for key, providers in POOLS.items():
            for provider in providers:
                assert provider.lower() in registered_providers, (
                    f"Pool {key} lists provider {provider!r} "
                    "but it has no registered capability"
                )


class TestRouterWithModuleSingleton:
    """Module-level singleton router is importable and functional."""

    def test_singleton_import(self):
        from vnstock.core.router import router

        assert isinstance(router, ProviderRouter)

    def test_singleton_pick(self):
        from vnstock.core.router import router

        router.reset()
        key = ("Market", "equity", "ohlcv")
        providers = POOLS.get(key, ["KBS"])
        picked = router.pick(key, providers)
        assert picked in providers

    def test_singleton_reset_affects_future_picks(self):
        from vnstock.core.router import router

        key = ("test_singleton", "ohlcv")
        providers = ["KBS", "VCI"]
        router.mark_failed(key, "KBS")
        router.reset()
        # After reset, KBS should be eligible again
        picks_after_reset = {router.pick(key, providers) for _ in range(4)}
        assert "KBS" in picks_after_reset
