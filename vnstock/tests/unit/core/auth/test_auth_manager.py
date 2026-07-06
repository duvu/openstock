"""Tests for AuthManager login/status/logout flows."""

from __future__ import annotations

import pytest

from vnstock.core.auth.credential_store import MemoryCredentialStore
from vnstock.core.auth.manager import AuthManager, AuthManagerError
from vnstock.core.auth.types import AuthType


def _make_tcbs_handler(token: str = "tcbs_token_abc"):
    """Return a mock TCBS login handler that returns a token dict."""

    def handler(provider: str, **kwargs) -> dict:
        username = kwargs.get("username", "")
        if not username:
            raise ValueError("username is required")
        return {"token": token, "_source": "mock"}

    return handler


class TestAuthManagerLogin:
    def test_login_succeeds_with_handler(self):
        store = MemoryCredentialStore()
        manager = AuthManager(store=store)
        manager.register_login_handler("tcbs", _make_tcbs_handler())

        ctx = manager.login("tcbs", username="105C123456", password="pass")
        assert ctx.authenticated is True
        assert ctx.auth_type == AuthType.BEARER_TOKEN
        assert ctx._token == "tcbs_token_abc"

    def test_login_stores_credentials(self):
        store = MemoryCredentialStore()
        manager = AuthManager(store=store)
        manager.register_login_handler("tcbs", _make_tcbs_handler("t1"))
        manager.login("tcbs", username="user", password="pass")
        assert store.has("tcbs")

    def test_login_no_handler_raises(self):
        manager = AuthManager()
        with pytest.raises(AuthManagerError, match="No login handler"):
            manager.login("unknown_provider")

    def test_login_handler_error_propagates(self):
        manager = AuthManager()
        manager.register_login_handler("tcbs", _make_tcbs_handler())
        with pytest.raises(ValueError, match="username is required"):
            manager.login("tcbs")  # no username

    def test_login_case_insensitive(self):
        store = MemoryCredentialStore()
        manager = AuthManager(store=store)
        manager.register_login_handler("TCBS", _make_tcbs_handler())
        ctx = manager.login("tcbs", username="user", password="pass")
        assert ctx.authenticated is True


class TestAuthManagerContext:
    def test_resolve_unauthenticated_when_no_creds(self):
        manager = AuthManager()
        ctx = manager.resolve_context("tcbs")
        assert ctx.authenticated is False
        assert ctx.auth_type == AuthType.NONE

    def test_resolve_from_store(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "from_store"})
        manager = AuthManager(store=store)
        ctx = manager.resolve_context("tcbs")
        assert ctx.authenticated is True
        assert ctx._token == "from_store"

    def test_context_does_not_expose_raw_creds_to_outside(self):
        """Ensure _credentials is never exposed."""
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "secret", "extra": "data"})
        manager = AuthManager(store=store)
        ctx = manager.resolve_context("tcbs")
        # _credentials should be None (not propagated to caller)
        assert ctx._credentials is None
        # safe_diagnostics should not contain token
        diag = ctx.safe_diagnostics()
        assert "token" not in diag
        assert "secret" not in str(diag)


class TestAuthManagerLogout:
    def test_logout_clears_session_cache(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "tok"})
        manager = AuthManager(store=store)
        # Populate cache
        manager.resolve_context("tcbs")
        assert manager._session_cache.is_cached("tcbs")
        # Logout clears cache
        manager.logout("tcbs")
        assert not manager._session_cache.is_cached("tcbs")
        # But store still has credentials
        assert store.has("tcbs")

    def test_delete_clears_store_and_cache(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "tok"})
        manager = AuthManager(store=store)
        manager.resolve_context("tcbs")
        manager.delete("tcbs")
        assert not store.has("tcbs")
        assert not manager._session_cache.is_cached("tcbs")
        ctx = manager.resolve_context("tcbs")
        assert ctx.authenticated is False


class TestAuthManagerStatus:
    def test_auth_status_unauthenticated(self):
        manager = AuthManager()
        status = manager.auth_status("tcbs")
        assert status["authenticated"] is False
        assert status["provider"] == "tcbs"
        assert "token" not in str(status)

    def test_auth_status_authenticated(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "tok"})
        manager = AuthManager(store=store)
        status = manager.auth_status("tcbs")
        assert status["authenticated"] is True
        assert "token" not in str(status)
        assert "tok" not in str(status)

    def test_auth_status_all(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "tok"})
        manager = AuthManager(store=store)
        statuses = manager.auth_status_all(["tcbs", "vci"])
        assert len(statuses) == 2
        providers = [s["provider"] for s in statuses]
        assert "tcbs" in providers
        assert "vci" in providers

    def test_has_credentials(self):
        store = MemoryCredentialStore()
        manager = AuthManager(store=store)
        assert manager.has_credentials("tcbs") is False
        store.write("tcbs", {"token": "tok"})
        assert manager.has_credentials("tcbs") is True
