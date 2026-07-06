"""
Unit tests for Phase 3 error model additions in exceptions.py.
"""

from __future__ import annotations

from vnstock.core.provider.exceptions import (
    NoHealthyProviderError,
    NoProviderForDatasetError,
    ProviderDisabledError,
    ProviderInCooldownError,
    VnstockPlatformError,
)


class TestNoProviderForDatasetError:
    def test_is_platform_error(self):
        err = NoProviderForDatasetError("equity.ohlcv")
        assert isinstance(err, VnstockPlatformError)

    def test_message_contains_dataset(self):
        err = NoProviderForDatasetError("equity.ohlcv")
        assert "equity.ohlcv" in str(err)

    def test_has_dataset_attribute(self):
        err = NoProviderForDatasetError("equity.ohlcv")
        assert err.dataset == "equity.ohlcv"


class TestNoHealthyProviderError:
    def test_is_platform_error(self):
        err = NoHealthyProviderError("equity.ohlcv")
        assert isinstance(err, VnstockPlatformError)

    def test_message_contains_dataset(self):
        err = NoHealthyProviderError("equity.ohlcv")
        assert "equity.ohlcv" in str(err)

    def test_message_lists_candidates(self):
        err = NoHealthyProviderError("equity.ohlcv", candidates=["KBS", "VCI"])
        assert "KBS" in str(err)
        assert "VCI" in str(err)

    def test_candidates_and_reasons_stored(self):
        err = NoHealthyProviderError(
            "equity.ohlcv",
            candidates=["KBS"],
            rejection_reasons={"KBS": "cooldown active"},
        )
        assert err.candidates == ["KBS"]
        assert err.rejection_reasons == {"KBS": "cooldown active"}


class TestProviderInCooldownError:
    def test_is_platform_error(self):
        err = ProviderInCooldownError("KBS", "equity.ohlcv")
        assert isinstance(err, VnstockPlatformError)

    def test_message_contains_provider_and_dataset(self):
        err = ProviderInCooldownError("KBS", "equity.ohlcv")
        assert "KBS" in str(err)
        assert "equity.ohlcv" in str(err)

    def test_cooldown_until_in_message(self):
        err = ProviderInCooldownError(
            "KBS", "equity.ohlcv", cooldown_until="2024-01-01T10:00:00"
        )
        assert "2024-01-01T10:00:00" in str(err)

    def test_attributes(self):
        err = ProviderInCooldownError("KBS", "equity.ohlcv", cooldown_until="X")
        assert err.provider_name == "KBS"
        assert err.dataset == "equity.ohlcv"
        assert err.cooldown_until == "X"


class TestProviderDisabledError:
    def test_is_platform_error(self):
        err = ProviderDisabledError("KBS", "equity.ohlcv")
        assert isinstance(err, VnstockPlatformError)

    def test_message_contains_provider(self):
        err = ProviderDisabledError("KBS", "equity.ohlcv")
        assert "KBS" in str(err)

    def test_notes_in_message(self):
        err = ProviderDisabledError("KBS", "equity.ohlcv", notes="maintenance")
        assert "maintenance" in str(err)

    def test_attributes(self):
        err = ProviderDisabledError("KBS", "equity.ohlcv", notes="down")
        assert err.provider_name == "KBS"
        assert err.dataset == "equity.ohlcv"
        assert err.notes == "down"
