"""
Unit tests for vnstock/core/provider/health.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from vnstock.core.provider.health import (
    DEFAULT_HEALTH_STORE,
    HealthStatus,
    InMemoryProviderHealthStore,
    ProviderHealth,
)

# ---------------------------------------------------------------------------
# ProviderHealth model
# ---------------------------------------------------------------------------


class TestProviderHealth:
    def test_default_status_is_unknown(self):
        h = ProviderHealth(provider="KBS", dataset="equity.ohlcv")
        assert h.status == HealthStatus.UNKNOWN

    def test_status_values_are_strings(self):
        for s in HealthStatus:
            assert isinstance(s.value, str)

    def test_not_in_cooldown_when_cooldown_until_is_none(self):
        h = ProviderHealth(provider="KBS", dataset="equity.ohlcv")
        assert not h.is_in_cooldown()

    def test_in_cooldown_when_future_timestamp(self):
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=60)
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", cooldown_until=future
        )
        assert h.is_in_cooldown()

    def test_not_in_cooldown_when_expired(self):
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
        h = ProviderHealth(provider="KBS", dataset="equity.ohlcv", cooldown_until=past)
        assert not h.is_in_cooldown()

    def test_to_dict_has_no_secrets(self):
        h = ProviderHealth(provider="KBS", dataset="equity.ohlcv")
        d = h.to_dict()
        forbidden = {"password", "api_key", "access_token", "authorization"}
        assert not forbidden & set(d.keys())

    def test_to_dict_status_is_string(self):
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", status=HealthStatus.HEALTHY
        )
        d = h.to_dict()
        assert d["status"] == "HEALTHY"
        assert isinstance(d["status"], str)

    def test_to_dict_serializes_timestamps(self):
        now = datetime.now(tz=timezone.utc)
        h = ProviderHealth(
            provider="KBS",
            dataset="equity.ohlcv",
            last_success_at=now,
            cooldown_until=now + timedelta(seconds=30),
        )
        d = h.to_dict()
        assert d["last_success_at"] is not None
        assert d["cooldown_until"] is not None


# ---------------------------------------------------------------------------
# InMemoryProviderHealthStore
# ---------------------------------------------------------------------------


class TestInMemoryProviderHealthStore:
    def setup_method(self):
        self.store = InMemoryProviderHealthStore()

    def test_get_missing_returns_unknown(self):
        h = self.store.get("KBS", "equity.ohlcv")
        assert h.status == HealthStatus.UNKNOWN
        assert h.provider == "KBS"
        assert h.dataset == "equity.ohlcv"

    def test_set_and_get_round_trip(self):
        h = ProviderHealth(
            provider="KBS", dataset="equity.ohlcv", status=HealthStatus.HEALTHY
        )
        self.store.set(h)
        retrieved = self.store.get("KBS", "equity.ohlcv")
        assert retrieved.status == HealthStatus.HEALTHY

    def test_provider_name_is_normalised_to_upper(self):
        h = ProviderHealth(
            provider="kbs", dataset="equity.ohlcv", status=HealthStatus.HEALTHY
        )
        self.store.set(h)
        assert self.store.get("KBS", "equity.ohlcv").status == HealthStatus.HEALTHY

    def test_record_success_sets_healthy(self):
        h = self.store.record_success("KBS", "equity.ohlcv", latency_ms=50.0)
        assert h.status == HealthStatus.HEALTHY
        assert h.latency_ms == 50.0
        assert h.failure_count == 0

    def test_record_success_increments_success_count(self):
        self.store.record_success("KBS", "equity.ohlcv")
        self.store.record_success("KBS", "equity.ohlcv")
        h = self.store.get("KBS", "equity.ohlcv")
        assert h.success_count == 2

    def test_record_success_clears_failure_count(self):
        now = datetime.now(tz=timezone.utc)
        self.store.record_failure("KBS", "equity.ohlcv", now=now)
        self.store.record_failure("KBS", "equity.ohlcv", now=now)
        self.store.record_success("KBS", "equity.ohlcv")
        h = self.store.get("KBS", "equity.ohlcv")
        assert h.failure_count == 0
        assert h.cooldown_until is None

    def test_first_failure_sets_degraded(self):
        h = self.store.record_failure("KBS", "equity.ohlcv", failure_threshold=3)
        assert h.status == HealthStatus.DEGRADED

    def test_threshold_failure_sets_failing_and_cooldown(self):
        now = datetime.now(tz=timezone.utc)
        for _ in range(3):
            h = self.store.record_failure(
                "KBS", "equity.ohlcv", failure_threshold=3, cooldown_seconds=60, now=now
            )
        assert h.status == HealthStatus.FAILING
        assert h.cooldown_until is not None
        assert h.cooldown_until > now

    def test_cooldown_expiry(self):
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=120)
        for _ in range(3):
            self.store.record_failure(
                "KBS",
                "equity.ohlcv",
                failure_threshold=3,
                cooldown_seconds=60,
                now=past,
            )
        h = self.store.get("KBS", "equity.ohlcv")
        assert not h.is_in_cooldown()  # cooldown already expired

    def test_list_for_dataset(self):
        self.store.record_success("KBS", "equity.ohlcv")
        self.store.record_failure("VCI", "equity.ohlcv")
        self.store.record_success("KBS", "equity.quote")
        entries = self.store.list_for_dataset("equity.ohlcv")
        names = {e.provider for e in entries}
        assert names == {"KBS", "VCI"}

    def test_clear(self):
        self.store.record_success("KBS", "equity.ohlcv")
        self.store.clear()
        assert len(self.store) == 0

    def test_default_health_store_is_instance(self):
        assert isinstance(DEFAULT_HEALTH_STORE, InMemoryProviderHealthStore)
