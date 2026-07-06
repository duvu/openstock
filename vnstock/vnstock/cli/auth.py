"""CLI auth commands for vnstock.

Provides the ``vnstock auth`` subcommand group:

  vnstock auth login PROVIDER     -- interactive login for a provider
  vnstock auth status [PROVIDER]  -- show auth status
  vnstock auth logout PROVIDER    -- clear in-memory auth session
  vnstock auth delete PROVIDER    -- delete stored credentials

Security:
  - Credentials are never printed to stdout or logged.
  - Token material is not displayed in any output.
  - Login is local and interactive; no REST endpoint is involved.

Usage::

    python -m vnstock.cli.auth login tcbs
    python -m vnstock.cli.auth status
    python -m vnstock.cli.auth status tcbs
    python -m vnstock.cli.auth logout tcbs
    python -m vnstock.cli.auth delete tcbs
"""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Optional


def _print(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Auth subcommands
# ---------------------------------------------------------------------------


def _get_manager():
    """Lazy-load AuthManager with LocalFileCredentialStore."""
    from vnstock.core.auth.credential_store import LocalFileCredentialStore
    from vnstock.core.auth.manager import AuthManager

    store = LocalFileCredentialStore()
    manager = AuthManager(store=store)

    # Register TCBS handler
    try:
        from vnstock.explorer.tcbs.auth_handler import tcbs_login_handler

        manager.register_login_handler("tcbs", tcbs_login_handler)
    except ImportError:
        pass

    return manager


def cmd_login(provider: str) -> int:
    """Interactive login for a provider.

    Currently only ``tcbs`` is supported.
    """
    provider = provider.lower()

    _print(f"Đăng nhập provider: {provider}")

    if provider == "tcbs":
        return _login_tcbs()
    else:
        _print(f"[LỖI] Provider '{provider}' không được hỗ trợ.")
        _print("  Provider được hỗ trợ: tcbs")
        return 1


def _login_tcbs() -> int:
    """Interactive TCBS login flow."""
    from vnstock.explorer.tcbs.auth import TCBSAuth, TCBSAuthError, TCBSOTPRequired

    _print("=" * 60)
    _print("  vnstock auth login — TCBS (Experimental)")
    _print("=" * 60)
    _print("CẢNH BÁO: TCBS auth là tính năng thử nghiệm.")
    _print("  Chỉ hỗ trợ đọc dữ liệu thị trường, không hỗ trợ lệnh/tài khoản.")
    _print("")

    try:
        username = input("Tên đăng nhập TCBS (VD: 105C123456): ").strip()
        if not username:
            _print("[LỖI] Tên đăng nhập không được để trống.")
            return 1
        password = getpass.getpass("Mật khẩu: ")
        if not password:
            _print("[LỖI] Mật khẩu không được để trống.")
            return 1
    except (KeyboardInterrupt, EOFError):
        _print("\n[HỦY] Đăng nhập bị hủy.")
        return 1

    auth = TCBSAuth()

    otp_session: Optional[str] = None
    token: Optional[str] = None

    try:
        _print("\nĐang xác thực...")
        token = auth.login(username=username, password=password)
        _print("[OK] Đăng nhập thành công (không cần OTP).")
    except TCBSOTPRequired as e:
        otp_session = e.otp_session
        _print("[INFO] TCBS yêu cầu mã OTP.")
    except TCBSAuthError as e:
        _print(f"\n[LỖI] Đăng nhập thất bại:\n  {e}")
        return 1

    if otp_session is not None:
        try:
            otp = input("Nhập mã OTP 6 chữ số từ ứng dụng TCInvest: ").strip()
            if not otp or len(otp) != 6 or not otp.isdigit():
                _print("[LỖI] Mã OTP phải gồm đúng 6 chữ số.")
                return 1
        except (KeyboardInterrupt, EOFError):
            _print("\n[HỦY] Đăng nhập bị hủy.")
            return 1

        try:
            _print("\nĐang xác thực OTP...")
            token = auth.confirm_otp(otp_session=otp_session, otp=otp)
            _print("[OK] Xác thực OTP thành công.")
        except TCBSAuthError as e:
            _print(f"\n[LỖI] Xác thực OTP thất bại:\n  {e}")
            return 1

    if token is None:
        _print("[LỖI] Không nhận được token từ TCBS.")
        return 1

    # Store via CredentialStore (never print the token)
    try:
        from vnstock.core.auth.credential_store import LocalFileCredentialStore

        store = LocalFileCredentialStore()
        store.write("tcbs", {"token": token, "_source": "tcbs_interactive"})
        _print("\n[OK] Thông tin xác thực đã lưu.")
        _print("  Dùng `vnstock auth status tcbs` để kiểm tra.")
    except Exception as exc:
        _print(f"\n[CẢNH BÁO] Không thể lưu thông tin xác thực: {exc}")
        _print("  Đặt TCBS_BEARER_TOKEN=<token> trong biến môi trường.")
        return 1

    _print("")
    return 0


def cmd_status(provider: Optional[str] = None) -> int:
    """Show auth status for one or all providers."""
    manager = _get_manager()

    if provider:
        provider = provider.lower()
        status = manager.auth_status(provider)
        _print_provider_status(provider, status)
    else:
        _print("Auth status:")
        _print("-" * 40)

        # auth_status_all() returns list[dict]
        all_status_list = manager.auth_status_all()
        for entry in all_status_list:
            p = entry.get("provider", "unknown")
            _print_provider_status(p, entry)

    return 0


def _print_provider_status(provider: str, status: dict) -> None:
    """Print a single provider's auth status."""
    authenticated = status.get("authenticated", False)
    state = "logged in" if authenticated else "not logged in"

    if authenticated:
        source = status.get("source", "unknown")
        _print(f"  {provider}: {state} (source: {source})")
    else:
        _print(f"  {provider}: {state}")


def cmd_logout(provider: str) -> int:
    """Clear the in-memory auth session for a provider."""
    provider = provider.lower()
    manager = _get_manager()

    try:
        manager.logout(provider)
        _print(f"[OK] Đã đăng xuất khỏi {provider}.")
        _print("  (Thông tin xác thực trên disk vẫn còn. Dùng `delete` để xóa.)")
    except Exception as exc:
        _print(f"[CẢNH BÁO] {exc}")

    return 0


def cmd_delete(provider: str) -> int:
    """Delete stored credentials for a provider."""
    provider = provider.lower()

    try:
        confirm = (
            input(f"Xóa thông tin xác thực của '{provider}'? [y/N]: ").strip().lower()
        )
    except (KeyboardInterrupt, EOFError):
        _print("\n[HỦY]")
        return 1

    if confirm not in ("y", "yes"):
        _print("[HỦY] Không xóa.")
        return 0

    manager = _get_manager()

    try:
        manager.delete(provider)
        _print(f"[OK] Đã xóa thông tin xác thực của {provider}.")
    except Exception as exc:
        _print(f"[LỖI] {exc}")
        return 1

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vnstock auth",
        description="Manage vnstock provider authentication.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # login
    login_parser = subparsers.add_parser(
        "login",
        help="Interactive login for a provider (e.g. tcbs).",
    )
    login_parser.add_argument(
        "provider",
        metavar="PROVIDER",
        help="Provider name (e.g. tcbs).",
    )

    # status
    status_parser = subparsers.add_parser(
        "status",
        help="Show auth status.",
    )
    status_parser.add_argument(
        "provider",
        metavar="PROVIDER",
        nargs="?",
        default=None,
        help="Optional provider name. If omitted, shows all.",
    )

    # logout
    logout_parser = subparsers.add_parser(
        "logout",
        help="Clear in-memory auth session for a provider.",
    )
    logout_parser.add_argument(
        "provider",
        metavar="PROVIDER",
        help="Provider name (e.g. tcbs).",
    )

    # delete
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete stored credentials for a provider.",
    )
    delete_parser.add_argument(
        "provider",
        metavar="PROVIDER",
        help="Provider name (e.g. tcbs).",
    )

    return parser


def main(argv=None) -> int:
    """Entry point for the ``vnstock auth`` CLI command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "login":
        return cmd_login(args.provider)
    elif args.subcommand == "status":
        return cmd_status(args.provider)
    elif args.subcommand == "logout":
        return cmd_logout(args.provider)
    elif args.subcommand == "delete":
        return cmd_delete(args.provider)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
