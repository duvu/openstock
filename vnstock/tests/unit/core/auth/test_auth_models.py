"""Tests for vnstock.core.auth — auth core models."""

from __future__ import annotations

import pytest

from vnstock.core.auth.context import AuthContext
from vnstock.core.auth.diagnostics import AuthDiagnostics
from vnstock.core.auth.policies import DEFAULT_AUTH_POLICY, AuthPolicy
from vnstock.core.auth.redaction import is_sensitive_key, redact, redact_dict
from vnstock.core.auth.session_cache import SessionCache
from vnstock.core.auth.spec import AuthSpec
from vnstock.core.auth.types import AuthType

# ---------------------------------------------------------------------------
# AuthType
# ---------------------------------------------------------------------------


class TestAuthType:
    def test_all_values_are_strings(self):
        for member in AuthType:
            assert isinstance(member.value, str)

    def test_none_value(self):
        assert AuthType.NONE.value == "none"

    def test_bearer_token_value(self):
        assert AuthType.BEARER_TOKEN.value == "bearer_token"

    def test_interactive_value(self):
        assert AuthType.INTERACTIVE.value == "interactive"


# ---------------------------------------------------------------------------
# AuthSpec
# ---------------------------------------------------------------------------


class TestAuthSpec:
    def test_no_auth_factory(self):
        spec = AuthSpec.no_auth()
        assert spec.auth_type == AuthType.NONE
        assert spec.required is False
        assert spec.experimental is False
        assert spec.explicit_only is False

    def test_tcbs_experimental_factory(self):
        spec = AuthSpec.tcbs_experimental(scopes=("equity.ohlcv",))
        assert spec.auth_type == AuthType.INTERACTIVE
        assert spec.required is True
        assert spec.experimental is True
        assert spec.explicit_only is True
        assert "equity.ohlcv" in spec.scopes

    def test_custom_spec(self):
        spec = AuthSpec(
            auth_type=AuthType.API_KEY,
            required=True,
            experimental=False,
            notes="FMP API key required.",
        )
        assert spec.auth_type == AuthType.API_KEY
        assert spec.required is True
        assert spec.notes == "FMP API key required."

    def test_frozen(self):
        spec = AuthSpec.no_auth()
        with pytest.raises((AttributeError, TypeError)):
            spec.required = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AuthContext
# ---------------------------------------------------------------------------


class TestAuthContext:
    def test_unauthenticated_factory(self):
        ctx = AuthContext.unauthenticated("KBS")
        assert ctx.provider == "KBS"
        assert ctx.authenticated is False
        assert ctx.auth_type == AuthType.NONE
        assert ctx._token is None

    def test_safe_diagnostics_no_secrets(self):
        ctx = AuthContext(
            provider="TCBS",
            auth_type=AuthType.BEARER_TOKEN,
            authenticated=True,
            credential_label="tcbs:local_file",
            _token="supersecrettoken",
        )
        diag = ctx.safe_diagnostics()
        assert "token" not in diag
        assert "_token" not in diag
        assert diag["authenticated"] is True
        assert diag["provider"] == "TCBS"
        assert diag["credential_label"] == "tcbs:local_file"

    def test_safe_diagnostics_unauthenticated(self):
        ctx = AuthContext.unauthenticated("VCI")
        diag = ctx.safe_diagnostics()
        assert diag["authenticated"] is False
        assert diag["auth_type"] == "none"


# ---------------------------------------------------------------------------
# AuthPolicy
# ---------------------------------------------------------------------------


class TestAuthPolicy:
    def test_all_policies_exist(self):
        policies = {p.value for p in AuthPolicy}
        assert "forbid_authenticated" in policies
        assert "prefer_no_auth" in policies
        assert "allow_authenticated" in policies
        assert "require_authenticated" in policies

    def test_default_is_prefer_no_auth(self):
        assert DEFAULT_AUTH_POLICY == AuthPolicy.PREFER_NO_AUTH


# ---------------------------------------------------------------------------
# SessionCache
# ---------------------------------------------------------------------------


class TestSessionCache:
    def test_set_and_get(self):
        cache = SessionCache()
        cache.set("tcbs", "token123", ttl_seconds=60)
        assert cache.get("tcbs") == "token123"

    def test_missing_returns_none(self):
        cache = SessionCache()
        assert cache.get("nonexistent") is None

    def test_is_cached(self):
        cache = SessionCache()
        assert not cache.is_cached("tcbs")
        cache.set("tcbs", "tok", ttl_seconds=60)
        assert cache.is_cached("tcbs")

    def test_delete(self):
        cache = SessionCache()
        cache.set("tcbs", "tok", ttl_seconds=60)
        cache.delete("tcbs")
        assert cache.get("tcbs") is None

    def test_clear(self):
        cache = SessionCache()
        cache.set("tcbs", "tok", ttl_seconds=60)
        cache.set("vci", "tok2", ttl_seconds=60)
        cache.clear()
        assert cache.get("tcbs") is None
        assert cache.get("vci") is None

    def test_expired_token_returns_none(self):
        cache = SessionCache()
        cache.set("tcbs", "tok", ttl_seconds=-1)  # already expired
        assert cache.get("tcbs") is None


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_redact_bearer_token(self):
        result = redact("Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
        assert "eyJ" not in result
        assert "[REDACTED]" in result

    def test_redact_plain_string_unchanged(self):
        result = redact("Hello, world!")
        assert result == "Hello, world!"

    def test_redact_dict_sensitive_keys(self):
        data = {"token": "secret123", "provider": "TCBS"}
        result = redact_dict(data)
        assert result["token"] == "[REDACTED]"
        assert result["provider"] == "TCBS"

    def test_redact_dict_nested(self):
        data = {"auth": {"token": "abc", "user": "foo"}, "name": "test"}
        result = redact_dict(data)
        assert result["auth"]["token"] == "[REDACTED]"
        assert result["auth"]["user"] == "foo"
        assert result["name"] == "test"

    def test_redact_dict_case_insensitive(self):
        data = {"TOKEN": "abc", "Password": "xyz"}
        result = redact_dict(data)
        assert result["TOKEN"] == "[REDACTED]"
        assert result["Password"] == "[REDACTED]"

    def test_is_sensitive_key(self):
        assert is_sensitive_key("token") is True
        assert is_sensitive_key("password") is True
        assert is_sensitive_key("provider") is False

    def test_redact_list(self):
        data = {"items": [{"token": "abc"}, {"name": "test"}]}
        result = redact_dict(data)
        assert result["items"][0]["token"] == "[REDACTED]"
        assert result["items"][1]["name"] == "test"


# ---------------------------------------------------------------------------
# AuthDiagnostics
# ---------------------------------------------------------------------------


class TestAuthDiagnostics:
    def test_unauthenticated_factory(self):
        diag = AuthDiagnostics.unauthenticated("KBS")
        assert diag.auth_used is False
        assert diag.auth_type == "none"
        assert diag.provider == "KBS"

    def test_to_dict_no_secrets(self):
        diag = AuthDiagnostics(
            provider="TCBS",
            auth_used=True,
            auth_type="bearer_token",
            credential_label="tcbs:local_file",
        )
        d = diag.to_dict()
        assert "token" not in d
        assert d["auth_used"] is True
        assert d["provider"] == "TCBS"

    def test_from_context(self):
        ctx = AuthContext(
            provider="TCBS",
            auth_type=AuthType.BEARER_TOKEN,
            authenticated=True,
            credential_label="tcbs:local_file",
            _token="secret",
        )
        diag = AuthDiagnostics.from_context(ctx)
        assert diag.auth_used is True
        assert diag.auth_type == "bearer_token"
        assert diag.credential_label == "tcbs:local_file"

    def test_scopes_defaults_to_empty_list(self):
        diag = AuthDiagnostics(provider="VCI", auth_used=False)
        d = diag.to_dict()
        assert d["scopes"] == []
