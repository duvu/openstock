"""Tests for TCBS auth handler (vnstock.explorer.tcbs.auth_handler).

Covers:
- tcbs_login_handler: successful login, OTP-required flow, failed login
- tcbs_otp_login_handler: successful OTP confirmation, failed OTP
- Safe error messages (no credential material leaked)
- Data-read-only scope validation
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vnstock.explorer.tcbs.auth import TCBSAuthError, TCBSOTPRequired
from vnstock.explorer.tcbs.auth_handler import (
    TCBSAuthHandlerError,
    tcbs_login_handler,
    tcbs_otp_login_handler,
)

# ---------------------------------------------------------------------------
# tcbs_login_handler
# ---------------------------------------------------------------------------


class TestTCBSLoginHandler:
    """Tests for tcbs_login_handler."""

    def test_successful_login_returns_credential_dict(self):
        """Should return dict with token, _source, _provider on success."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.return_value = "eyJhbGciOiJSUzI1NiJ9.testtoken"
            MockAuth.return_value = instance

            result = tcbs_login_handler(
                provider="tcbs",
                username="105C123456",
                password="mypassword",
            )

        assert result["token"] == "eyJhbGciOiJSUzI1NiJ9.testtoken"
        assert result["_source"] == "tcbs_interactive"
        assert result["_provider"] == "tcbs"

    def test_successful_login_with_otp_inline(self):
        """Should pass otp to auth.login when provided."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.return_value = "token_with_otp"
            MockAuth.return_value = instance

            result = tcbs_login_handler(
                provider="tcbs",
                username="105C123456",
                password="mypassword",
                otp="123456",
            )

        assert result["token"] == "token_with_otp"
        instance.login.assert_called_once_with(
            username="105C123456", password="mypassword", otp="123456"
        )

    def test_otp_required_is_reraised(self):
        """TCBSOTPRequired from auth.login must bubble up unchanged."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.side_effect = TCBSOTPRequired(otp_session="sess_abc123")
            MockAuth.return_value = instance

            with pytest.raises(TCBSOTPRequired) as exc_info:
                tcbs_login_handler(
                    provider="tcbs",
                    username="105C123456",
                    password="mypassword",
                )

        assert exc_info.value.otp_session == "sess_abc123"

    def test_auth_error_is_wrapped_safely(self):
        """TCBSAuthError must be wrapped in TCBSAuthHandlerError with safe message."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.side_effect = TCBSAuthError(
                "Sai mật khẩu — password=secret123"
            )
            MockAuth.return_value = instance

            with pytest.raises(TCBSAuthHandlerError) as exc_info:
                tcbs_login_handler(
                    provider="tcbs",
                    username="105C123456",
                    password="secret123",
                )

        error_msg = str(exc_info.value)
        # Must not expose password
        assert "secret123" not in error_msg
        # Should have a safe message
        assert "authentication failed" in error_msg.lower() or "TCBS" in error_msg

    def test_missing_username_raises_handler_error(self):
        """Should raise TCBSAuthHandlerError when username is empty."""
        with pytest.raises(TCBSAuthHandlerError, match="username"):
            tcbs_login_handler(provider="tcbs", username="", password="mypassword")

    def test_missing_password_raises_handler_error(self):
        """Should raise TCBSAuthHandlerError when password is empty."""
        with pytest.raises(TCBSAuthHandlerError, match="password"):
            tcbs_login_handler(provider="tcbs", username="105C123456", password="")

    def test_timeout_forwarded_to_tcbs_auth(self):
        """Should pass timeout to TCBSAuth constructor."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.return_value = "tok"
            MockAuth.return_value = instance

            tcbs_login_handler(
                provider="tcbs",
                username="105C123456",
                password="pass",
                timeout=30,
            )

        MockAuth.assert_called_once_with(timeout=30)

    def test_result_has_no_username_or_password(self):
        """Returned credential dict must not contain username or password."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.return_value = "clean_token"
            MockAuth.return_value = instance

            result = tcbs_login_handler(
                provider="tcbs",
                username="105C123456",
                password="verysecret",
            )

        result_str = str(result)
        assert "verysecret" not in result_str
        assert "username" not in result
        assert "password" not in result


# ---------------------------------------------------------------------------
# tcbs_otp_login_handler
# ---------------------------------------------------------------------------


class TestTCBSOTPLoginHandler:
    """Tests for tcbs_otp_login_handler."""

    def test_successful_otp_confirmation_returns_credential_dict(self):
        """Should return dict with token, _source, _provider on success."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.confirm_otp.return_value = "otp_confirmed_token"
            MockAuth.return_value = instance

            result = tcbs_otp_login_handler(
                provider="tcbs",
                username="105C123456",
                password="mypassword",
                otp_session="sess_xyz",
                otp="654321",
            )

        assert result["token"] == "otp_confirmed_token"
        assert result["_source"] == "tcbs_interactive"
        assert result["_provider"] == "tcbs"

    def test_otp_passed_to_confirm_otp(self):
        """Should call confirm_otp with correct otp_session and otp."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.confirm_otp.return_value = "tok"
            MockAuth.return_value = instance

            tcbs_otp_login_handler(
                provider="tcbs",
                username="user",
                password="pass",
                otp_session="my_session_id",
                otp="111222",
            )

        instance.confirm_otp.assert_called_once_with(
            otp_session="my_session_id", otp="111222"
        )

    def test_auth_error_wrapped_safely(self):
        """TCBSAuthError from confirm_otp must be wrapped safely."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.confirm_otp.side_effect = TCBSAuthError("OTP sai — secret_data")
            MockAuth.return_value = instance

            with pytest.raises(TCBSAuthHandlerError) as exc_info:
                tcbs_otp_login_handler(
                    provider="tcbs",
                    username="user",
                    password="pass",
                    otp_session="sess",
                    otp="000000",
                )

        error_msg = str(exc_info.value)
        assert "secret_data" not in error_msg
        assert "OTP" in error_msg or "otp" in error_msg.lower()

    def test_missing_otp_session_raises_handler_error(self):
        """Should raise TCBSAuthHandlerError when otp_session is empty."""
        with pytest.raises(TCBSAuthHandlerError, match="otp_session"):
            tcbs_otp_login_handler(
                provider="tcbs",
                username="user",
                password="pass",
                otp_session="",
                otp="123456",
            )

    def test_missing_otp_raises_handler_error(self):
        """Should raise TCBSAuthHandlerError when otp is empty."""
        with pytest.raises(TCBSAuthHandlerError, match="otp"):
            tcbs_otp_login_handler(
                provider="tcbs",
                username="user",
                password="pass",
                otp_session="session_id",
                otp="",
            )

    def test_result_has_no_password_material(self):
        """Returned dict must not contain password."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.confirm_otp.return_value = "tok"
            MockAuth.return_value = instance

            result = tcbs_otp_login_handler(
                provider="tcbs",
                username="user",
                password="supersecret",
                otp_session="sess",
                otp="123456",
            )

        result_str = str(result)
        assert "supersecret" not in result_str
        assert "password" not in result


# ---------------------------------------------------------------------------
# Data-read scope validation
# ---------------------------------------------------------------------------


class TestTCBSDataReadScope:
    """Verify TCBS auth handler is data-read only (no broker/account ops)."""

    def test_handler_has_no_account_methods(self):
        """auth_handler must not expose account, order, portfolio methods."""
        import vnstock.explorer.tcbs.auth_handler as mod

        forbidden_names = {
            "account",
            "order",
            "portfolio",
            "transfer",
            "margin",
            "iCopy",
            "execute_order",
            "cancel_order",
        }
        exported = set(dir(mod))
        found_forbidden = exported & forbidden_names
        assert not found_forbidden, (
            f"auth_handler exposes forbidden names: {found_forbidden}"
        )

    def test_tcbs_auth_spec_is_experimental(self):
        """TCBSProviderPlugin.auth_spec() must be experimental and explicit_only."""
        from vnstock.providers.tcbs.plugin import TCBSProviderPlugin

        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("quote")
        assert spec.experimental is True
        assert spec.explicit_only is True

    def test_tcbs_auth_spec_has_no_forbidden_scopes(self):
        """TCBS auth spec must not include account, order, portfolio, transfer, margin."""
        from vnstock.providers.tcbs.plugin import TCBSProviderPlugin

        plugin = TCBSProviderPlugin()
        spec = plugin.auth_spec("quote")
        if spec.scopes:
            forbidden_scopes = {
                "account",
                "order",
                "portfolio",
                "transfer",
                "margin",
            }
            found = set(spec.scopes) & forbidden_scopes
            assert not found, f"TCBS auth spec has forbidden scopes: {found}"

    def test_login_handler_returns_only_safe_keys(self):
        """Credential dict from handler must contain only token and metadata."""
        with patch("vnstock.explorer.tcbs.auth_handler.TCBSAuth") as MockAuth:
            instance = MagicMock()
            instance.login.return_value = "safe_token"
            MockAuth.return_value = instance

            result = tcbs_login_handler(
                provider="tcbs",
                username="user",
                password="pass",
            )

        allowed_keys = {"token", "_source", "_provider"}
        extra_keys = set(result.keys()) - allowed_keys
        assert not extra_keys, f"Unexpected keys in credential dict: {extra_keys}"
