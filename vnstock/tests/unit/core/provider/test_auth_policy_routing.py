"""Tests for auth policy-aware PluginRouter.

Covers:
- FORBID_AUTHENTICATED: only public providers selected
- PREFER_NO_AUTH: public first, authenticated as fallback
- ALLOW_AUTHENTICATED: no filter (current behavior)
- REQUIRE_AUTHENTICATED: only authenticated providers selected
- Auth policy + health policy combination
- Default auth policy (PREFER_NO_AUTH)
"""

from __future__ import annotations

import pytest

from tests.fixtures.fake_provider import FakeProviderPlugin
from vnstock.core.auth.policies import AuthPolicy
from vnstock.core.auth.spec import AuthSpec
from vnstock.core.auth.types import AuthType
from vnstock.core.provider.exceptions import (
    NoHealthyProviderError,
)
from vnstock.core.provider.health import (
    HealthStatus,
    InMemoryProviderHealthStore,
    ProviderHealth,
)
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.provider.plugin_router import PluginRouter, _provider_requires_auth

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class PublicProviderPlugin(FakeProviderPlugin):
    """Provider with no auth required (e.g. KBS, VCI)."""

    def auth_spec(self, dataset: str) -> AuthSpec:
        return AuthSpec.no_auth()


class AuthProviderPlugin(FakeProviderPlugin):
    """Provider that requires authentication (e.g. FMP with API key)."""

    def auth_spec(self, dataset: str) -> AuthSpec:
        return AuthSpec(
            auth_type=AuthType.API_KEY,
            required=True,
            experimental=False,
            explicit_only=False,
        )


class ExperimentalAuthProviderPlugin(FakeProviderPlugin):
    """Provider that requires experimental authentication (e.g. TCBS)."""

    def auth_spec(self, dataset: str) -> AuthSpec:
        return AuthSpec.tcbs_experimental()


class NoAuthSpecProviderPlugin(FakeProviderPlugin):
    """Provider without auth_spec method (legacy, treat as public)."""

    # Intentionally no auth_spec method


@pytest.fixture
def public_provider():
    return PublicProviderPlugin("KBS", ["equity.ohlcv", "equity.quote"])


@pytest.fixture
def auth_provider():
    return AuthProviderPlugin("FMP", ["equity.ohlcv"])


@pytest.fixture
def tcbs_provider():
    return ExperimentalAuthProviderPlugin("TCBS", ["equity.ohlcv"])


@pytest.fixture
def no_auth_spec_provider():
    return NoAuthSpecProviderPlugin("LEGACY", ["equity.ohlcv"])


@pytest.fixture
def mixed_registry(public_provider, auth_provider, tcbs_provider):
    reg = PluginRegistry()
    reg.register(public_provider)
    reg.register(auth_provider)
    reg.register(tcbs_provider)
    return reg


@pytest.fixture
def health_store():
    return InMemoryProviderHealthStore()


@pytest.fixture
def router(mixed_registry, health_store):
    return PluginRouter(
        mixed_registry,
        default_priority=["KBS", "FMP", "TCBS"],
        health_store=health_store,
    )


# ---------------------------------------------------------------------------
# _provider_requires_auth helper
# ---------------------------------------------------------------------------


class TestProviderRequiresAuth:
    def test_public_provider_is_not_auth(self, public_provider):
        assert _provider_requires_auth(public_provider, "equity.ohlcv") is False

    def test_api_key_provider_requires_auth(self, auth_provider):
        assert _provider_requires_auth(auth_provider, "equity.ohlcv") is True

    def test_tcbs_experimental_requires_auth(self, tcbs_provider):
        assert _provider_requires_auth(tcbs_provider, "equity.ohlcv") is True

    def test_provider_without_auth_spec_is_public(self, no_auth_spec_provider):
        """Providers without auth_spec are treated as public (safe default)."""
        assert _provider_requires_auth(no_auth_spec_provider, "equity.ohlcv") is False


# ---------------------------------------------------------------------------
# ALLOW_AUTHENTICATED (no filter — current behavior)
# ---------------------------------------------------------------------------


class TestAllowAuthenticated:
    def test_selects_highest_priority_regardless_of_auth(self, router):
        """ALLOW_AUTHENTICATED must not filter any provider."""
        provider = router.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.ALLOW_AUTHENTICATED
        )
        assert provider.name == "KBS"

    def test_does_not_reject_auth_providers(self, mixed_registry, health_store):
        """Only FMP registered; must be selectable with ALLOW_AUTHENTICATED."""
        reg = PluginRegistry()
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)
        provider = r.resolve("equity.ohlcv", auth_policy=AuthPolicy.ALLOW_AUTHENTICATED)
        assert provider.name == "FMP"


# ---------------------------------------------------------------------------
# FORBID_AUTHENTICATED
# ---------------------------------------------------------------------------


class TestForbidAuthenticated:
    def test_selects_public_provider_only(self, router):
        """FORBID_AUTHENTICATED must pick KBS (public)."""
        provider = router.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED
        )
        assert provider.name == "KBS"

    def test_rejects_auth_provider_with_reason(self, router):
        """Authenticated providers (FMP, TCBS) appear in rejected dict."""
        router.resolve("equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED)
        decision = router.last_decision
        assert decision is not None
        # FMP and TCBS should be rejected
        assert "FMP" in decision.rejected or "TCBS" in decision.rejected

    def test_raises_no_healthy_provider_when_all_require_auth(self, health_store):
        """When only authenticated providers exist, must raise NoHealthyProviderError."""
        reg = PluginRegistry()
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        reg.register(ExperimentalAuthProviderPlugin("TCBS", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        with pytest.raises(NoHealthyProviderError):
            r.resolve("equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED)

    def test_public_provider_still_available_when_auth_providers_rejected(self, router):
        """Ensure public KBS is always selectable when FORBID_AUTHENTICATED."""
        provider = router.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED
        )
        assert provider.name == "KBS"
        assert provider.name not in {"FMP", "TCBS"}


# ---------------------------------------------------------------------------
# PREFER_NO_AUTH
# ---------------------------------------------------------------------------


class TestPreferNoAuth:
    def test_prefers_public_over_auth_provider(self, router):
        """PREFER_NO_AUTH must select KBS (public) over FMP/TCBS (auth)."""
        provider = router.resolve("equity.ohlcv", auth_policy=AuthPolicy.PREFER_NO_AUTH)
        assert provider.name == "KBS"

    def test_falls_back_to_auth_when_only_auth_available(self, health_store):
        """When no public provider registered, fall back to auth provider."""
        reg = PluginRegistry()
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        provider = r.resolve("equity.ohlcv", auth_policy=AuthPolicy.PREFER_NO_AUTH)
        assert provider.name == "FMP"

    def test_falls_back_to_auth_when_public_in_cooldown(
        self, mixed_registry, health_store
    ):
        """When public provider is in cooldown, authenticated provider should be selected."""

        health_store.record_failure("KBS", "equity.ohlcv", cooldown_seconds=3600)
        r = PluginRouter(
            mixed_registry,
            default_priority=["KBS", "FMP", "TCBS"],
            health_store=health_store,
        )
        # KBS is in cooldown; FMP or TCBS should be selected
        provider = r.resolve("equity.ohlcv", auth_policy=AuthPolicy.PREFER_NO_AUTH)
        assert provider.name in {"FMP", "TCBS"}

    def test_is_default_auth_policy(self, router):
        """Default auth policy must be PREFER_NO_AUTH."""
        assert router.default_auth_policy == AuthPolicy.PREFER_NO_AUTH


# ---------------------------------------------------------------------------
# REQUIRE_AUTHENTICATED
# ---------------------------------------------------------------------------


class TestRequireAuthenticated:
    def test_selects_auth_provider(self, health_store):
        """REQUIRE_AUTHENTICATED must pick an authenticated provider."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        provider = r.resolve(
            "equity.ohlcv", auth_policy=AuthPolicy.REQUIRE_AUTHENTICATED
        )
        assert provider.name == "FMP"

    def test_rejects_public_providers(self, health_store):
        """Public providers should appear in rejected when REQUIRE_AUTHENTICATED."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        r.resolve("equity.ohlcv", auth_policy=AuthPolicy.REQUIRE_AUTHENTICATED)
        decision = r.last_decision
        assert decision is not None
        assert "KBS" in decision.rejected

    def test_raises_when_no_auth_providers_available(self, health_store):
        """When only public providers exist, must raise NoHealthyProviderError."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(PublicProviderPlugin("VCI", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        with pytest.raises(NoHealthyProviderError):
            r.resolve("equity.ohlcv", auth_policy=AuthPolicy.REQUIRE_AUTHENTICATED)


# ---------------------------------------------------------------------------
# Auth policy + health policy combination
# ---------------------------------------------------------------------------


class TestAuthPolicyPlusHealthPolicy:
    def test_forbid_authenticated_plus_health_disabled(self, health_store):
        """FORBID_AUTHENTICATED + DISABLED public provider = NoHealthyProvider."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))
        r = PluginRouter(reg, health_store=health_store)

        # Disable the only public provider
        health_store.set(
            ProviderHealth(
                provider="KBS", dataset="equity.ohlcv", status=HealthStatus.DISABLED
            )
        )

        with pytest.raises(NoHealthyProviderError):
            r.resolve("equity.ohlcv", auth_policy=AuthPolicy.FORBID_AUTHENTICATED)

    def test_prefer_no_auth_falls_back_to_degraded_public(self, health_store):
        """PREFER_NO_AUTH: degraded public provider selected when auth provider is failing."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))

        from vnstock.core.provider.routing import RoutingPolicy

        policy = RoutingPolicy(
            prefer_healthy=True,
            allow_degraded=True,
            allow_failing_fallback=False,  # FAILING not allowed
            respect_cooldown=True,
        )
        r = PluginRouter(reg, health_store=health_store, policy=policy)

        # KBS is DEGRADED, FMP is FAILING (worse than DEGRADED)
        health_store.set(
            ProviderHealth(
                provider="KBS", dataset="equity.ohlcv", status=HealthStatus.DEGRADED
            )
        )
        health_store.set(
            ProviderHealth(
                provider="FMP", dataset="equity.ohlcv", status=HealthStatus.FAILING
            )
        )

        provider = r.resolve("equity.ohlcv", auth_policy=AuthPolicy.PREFER_NO_AUTH)
        # KBS (degraded, public) should be selected — FMP is FAILING and not allowed
        assert provider.name == "KBS"

    def test_authenticated_not_selected_by_default(self, router):
        """Default policy (PREFER_NO_AUTH) must NOT select authenticated providers
        when public providers are available."""
        provider = router.resolve("equity.ohlcv")
        assert provider.name == "KBS"
        assert provider.name != "FMP"
        assert provider.name != "TCBS"


# ---------------------------------------------------------------------------
# Default auth policy on PluginRouter
# ---------------------------------------------------------------------------


class TestDefaultAuthPolicy:
    def test_default_auth_policy_is_prefer_no_auth(self):
        """PluginRouter.default_auth_policy must default to PREFER_NO_AUTH."""
        from vnstock.core.provider.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        r = PluginRouter(reg)
        assert r.default_auth_policy == AuthPolicy.PREFER_NO_AUTH

    def test_custom_default_auth_policy_stored(self):
        """Custom default_auth_policy must be stored and used."""
        reg = PluginRegistry()
        r = PluginRouter(reg, default_auth_policy=AuthPolicy.ALLOW_AUTHENTICATED)
        assert r.default_auth_policy == AuthPolicy.ALLOW_AUTHENTICATED

    def test_resolve_uses_default_auth_policy(self, health_store):
        """resolve() without explicit auth_policy must use default_auth_policy."""
        reg = PluginRegistry()
        reg.register(PublicProviderPlugin("KBS", ["equity.ohlcv"]))
        reg.register(AuthProviderPlugin("FMP", ["equity.ohlcv"]))

        # Default policy is PREFER_NO_AUTH — public should win
        r = PluginRouter(
            reg,
            health_store=health_store,
            default_auth_policy=AuthPolicy.PREFER_NO_AUTH,
        )
        provider = r.resolve("equity.ohlcv")
        assert provider.name == "KBS"
