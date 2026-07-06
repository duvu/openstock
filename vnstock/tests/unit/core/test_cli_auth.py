"""Tests for vnstock.cli.auth module.

Covers:
- cmd_login: dispatches to TCBS login flow
- cmd_status: shows single or all-providers status
- cmd_logout: clears session
- cmd_delete: deletes stored credentials after confirmation
- main(): argument parsing and dispatch
- No sensitive credential material is printed
"""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

from vnstock.cli.auth import (
    cmd_delete,
    cmd_login,
    cmd_logout,
    cmd_status,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_output(func, *args, **kwargs):
    """Run func, capture stdout, return (result, output_str)."""
    old_stdout = sys.stdout
    sys.stdout = buf = StringIO()
    try:
        result = func(*args, **kwargs)
    finally:
        sys.stdout = old_stdout
    return result, buf.getvalue()


# ---------------------------------------------------------------------------
# cmd_login
# ---------------------------------------------------------------------------


class TestCmdLogin:
    def test_unknown_provider_returns_1(self):
        result, output = _capture_output(cmd_login, "foobar")
        assert result == 1
        assert "foobar" in output

    def test_tcbs_empty_username_returns_1(self):
        with patch("builtins.input", return_value=""):
            result, output = _capture_output(cmd_login, "tcbs")
        assert result == 1
        assert (
            "tên đăng nhập" in output.lower()
            or "username" in output.lower()
            or "LỖI" in output
        )

    def test_tcbs_empty_password_returns_1(self):
        with patch("builtins.input", return_value="105C123456"):
            with patch("getpass.getpass", return_value=""):
                result, output = _capture_output(cmd_login, "tcbs")
        assert result == 1

    def test_tcbs_keyboard_interrupt_returns_1(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result, output = _capture_output(cmd_login, "tcbs")
        assert result == 1
        assert "HỦY" in output

    def test_tcbs_successful_login_stores_credentials_returns_0(self):
        from vnstock.explorer.tcbs.auth import TCBSAuth

        with (
            patch("builtins.input", return_value="105C123456"),
            patch("getpass.getpass", return_value="mypass"),
            patch.object(TCBSAuth, "login", return_value="fake_jwt_token"),
            patch(
                "vnstock.core.auth.credential_store.LocalFileCredentialStore.write"
            ) as mock_write,
        ):
            result, output = _capture_output(cmd_login, "tcbs")

        assert result == 0
        mock_write.assert_called_once()
        # Token must not appear in output
        assert "fake_jwt_token" not in output

    def test_tcbs_otp_required_then_success(self):
        from vnstock.explorer.tcbs.auth import TCBSAuth, TCBSOTPRequired

        with (
            patch("builtins.input", side_effect=["105C123456", "123456"]),
            patch("getpass.getpass", return_value="mypass"),
            patch.object(TCBSAuth, "login", side_effect=TCBSOTPRequired("sess_xyz")),
            patch.object(TCBSAuth, "confirm_otp", return_value="jwt_after_otp"),
            patch("vnstock.core.auth.credential_store.LocalFileCredentialStore.write"),
        ):
            result, output = _capture_output(cmd_login, "tcbs")

        assert result == 0
        assert "jwt_after_otp" not in output

    def test_tcbs_login_auth_error_returns_1(self):
        from vnstock.explorer.tcbs.auth import TCBSAuth, TCBSAuthError

        with (
            patch("builtins.input", return_value="105C123456"),
            patch("getpass.getpass", return_value="wrongpass"),
            patch.object(TCBSAuth, "login", side_effect=TCBSAuthError("Sai mật khẩu")),
        ):
            result, output = _capture_output(cmd_login, "tcbs")

        assert result == 1
        assert "LỖI" in output
        # Should NOT expose the password
        assert "wrongpass" not in output

    def test_tcbs_provider_name_is_case_insensitive(self):
        with patch("builtins.input", return_value=""):
            result, _ = _capture_output(cmd_login, "TCBS")
        assert result == 1  # empty username, but provider was recognized

    def test_no_token_printed_on_success(self):
        from vnstock.explorer.tcbs.auth import TCBSAuth

        with (
            patch("builtins.input", return_value="105C123456"),
            patch("getpass.getpass", return_value="mypass"),
            patch.object(TCBSAuth, "login", return_value="supersecret_jwt"),
            patch("vnstock.core.auth.credential_store.LocalFileCredentialStore.write"),
        ):
            result, output = _capture_output(cmd_login, "tcbs")

        # Token must NEVER appear in output
        assert "supersecret_jwt" not in output


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


class TestCmdStatus:
    def _make_manager(self, status_data=None):
        mock = MagicMock()
        if status_data:
            mock.auth_status.side_effect = lambda p: status_data.get(
                p, {"authenticated": False, "provider": p}
            )
            # auth_status_all() returns list[dict] in the updated API
            mock.auth_status_all.return_value = list(status_data.values())
        else:
            mock.auth_status.return_value = {"authenticated": False, "provider": "tcbs"}
            mock.auth_status_all.return_value = []
        return mock

    def test_status_single_provider_unauthenticated(self):
        mock_mgr = self._make_manager()
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_status, "tcbs")
        assert result == 0
        assert "tcbs" in output
        assert "not logged in" in output

    def test_status_single_provider_authenticated(self):
        mock_mgr = self._make_manager(
            {
                "tcbs": {
                    "authenticated": True,
                    "provider": "tcbs",
                    "source": "tcbs_interactive",
                }
            }
        )
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_status, "tcbs")
        assert result == 0
        assert "logged in" in output
        assert "tcbs_interactive" in output

    def test_status_all_providers(self):
        mock_mgr = self._make_manager(
            {
                "tcbs": {
                    "authenticated": True,
                    "provider": "tcbs",
                    "source": "tcbs_interactive",
                },
            }
        )
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_status, None)
        assert result == 0
        assert "tcbs" in output

    def test_status_does_not_print_token(self):
        mock_mgr = self._make_manager(
            {
                "tcbs": {
                    "authenticated": True,
                    "provider": "tcbs",
                    "source": "tcbs_interactive",
                    "token": "should_not_appear",
                }
            }
        )
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_status, "tcbs")
        assert "should_not_appear" not in output


# ---------------------------------------------------------------------------
# cmd_logout
# ---------------------------------------------------------------------------


class TestCmdLogout:
    def test_logout_calls_manager_logout(self):
        mock_mgr = MagicMock()
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_logout, "tcbs")
        mock_mgr.logout.assert_called_once_with("tcbs")
        assert result == 0
        assert "tcbs" in output

    def test_logout_is_case_insensitive(self):
        mock_mgr = MagicMock()
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_logout, "TCBS")
        mock_mgr.logout.assert_called_once_with("tcbs")

    def test_logout_exception_returns_0_with_warning(self):
        mock_mgr = MagicMock()
        mock_mgr.logout.side_effect = Exception("session not found")
        with patch("vnstock.cli.auth._get_manager", return_value=mock_mgr):
            result, output = _capture_output(cmd_logout, "tcbs")
        # Should warn but not crash
        assert result == 0


# ---------------------------------------------------------------------------
# cmd_delete
# ---------------------------------------------------------------------------


class TestCmdDelete:
    def test_delete_confirmed_calls_manager_delete(self):
        mock_mgr = MagicMock()
        with (
            patch("vnstock.cli.auth._get_manager", return_value=mock_mgr),
            patch("builtins.input", return_value="y"),
        ):
            result, output = _capture_output(cmd_delete, "tcbs")
        mock_mgr.delete.assert_called_once_with("tcbs")
        assert result == 0

    def test_delete_not_confirmed_does_not_call_delete(self):
        mock_mgr = MagicMock()
        with (
            patch("vnstock.cli.auth._get_manager", return_value=mock_mgr),
            patch("builtins.input", return_value="n"),
        ):
            result, output = _capture_output(cmd_delete, "tcbs")
        mock_mgr.delete.assert_not_called()
        assert result == 0

    def test_delete_keyboard_interrupt_returns_1(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result, output = _capture_output(cmd_delete, "tcbs")
        assert result == 1

    def test_delete_exception_returns_1(self):
        mock_mgr = MagicMock()
        mock_mgr.delete.side_effect = Exception("not found")
        with (
            patch("vnstock.cli.auth._get_manager", return_value=mock_mgr),
            patch("builtins.input", return_value="y"),
        ):
            result, output = _capture_output(cmd_delete, "tcbs")
        assert result == 1


# ---------------------------------------------------------------------------
# build_parser / main()
# ---------------------------------------------------------------------------


class TestMainArgParsing:
    def test_no_subcommand_prints_help_returns_1(self):
        result, output = _capture_output(main, [])
        assert result == 1

    def test_login_dispatched_correctly(self):
        with patch("vnstock.cli.auth.cmd_login", return_value=0) as mock_login:
            result = main(["login", "tcbs"])
        mock_login.assert_called_once_with("tcbs")
        assert result == 0

    def test_status_dispatched_correctly(self):
        with patch("vnstock.cli.auth.cmd_status", return_value=0) as mock_status:
            main(["status"])
        mock_status.assert_called_once_with(None)

    def test_status_with_provider_dispatched_correctly(self):
        with patch("vnstock.cli.auth.cmd_status", return_value=0) as mock_status:
            main(["status", "tcbs"])
        mock_status.assert_called_once_with("tcbs")

    def test_logout_dispatched_correctly(self):
        with patch("vnstock.cli.auth.cmd_logout", return_value=0) as mock_logout:
            main(["logout", "tcbs"])
        mock_logout.assert_called_once_with("tcbs")

    def test_delete_dispatched_correctly(self):
        with patch("vnstock.cli.auth.cmd_delete", return_value=0) as mock_delete:
            main(["delete", "tcbs"])
        mock_delete.assert_called_once_with("tcbs")

    def test_legacy_tcbs_login_still_documented(self):
        """vnstock-tcbs-login script entry must still exist in pyproject.toml."""
        import pathlib

        pyproject = pathlib.Path(__file__).parents[3] / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            assert "vnstock-tcbs-login" in content, (
                "Legacy vnstock-tcbs-login script must remain for backward compat"
            )
