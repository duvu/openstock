"""TCBS auth handler for AuthManager integration.

Provides a login handler callable that wraps the existing TCBSAuth
interactive flow for use with AuthManager.

Usage::

    from vnstock.core.auth.manager import AuthManager
    from vnstock.core.auth.credential_store import LocalFileCredentialStore
    from vnstock.explorer.tcbs.auth_handler import tcbs_login_handler

    store = LocalFileCredentialStore()
    manager = AuthManager(store=store)
    manager.register_login_handler("tcbs", tcbs_login_handler)

    # Interactive login (called from CLI):
    ctx = manager.login("tcbs", username="105C123456", password="mypass")

    # Resolve context for data request:
    ctx = manager.resolve_context("tcbs")
    token = ctx._token  # use for authenticated TCBS requests

Scope: data-read only. No account, order, portfolio, transfer, or margin.
"""

from __future__ import annotations

from typing import Any, Optional

from vnstock.explorer.tcbs.auth import TCBSAuth, TCBSAuthError, TCBSOTPRequired


class TCBSAuthHandlerError(Exception):
    """Raised when the TCBS auth handler fails."""


def tcbs_login_handler(
    provider: str,
    username: str = "",
    password: str = "",
    otp: Optional[str] = None,
    timeout: int = 15,
    **kwargs: Any,
) -> dict[str, Any]:
    """AuthManager login handler for TCBS.

    Wraps the TCBSAuth interactive flow and returns a credential dict.
    Sensitive fields (token) are returned for storage — callers must
    handle this dict only through AuthManager/CredentialStore and must
    never log or print it.

    Args:
        provider: Must be ``"tcbs"`` (case-insensitive).
        username: TCBS account ID (e.g. ``"105C123456"``).
        password: Account password.
        otp: Optional 6-digit OTP if pre-obtained.
        timeout: HTTP timeout seconds.
        **kwargs: Ignored extra kwargs.

    Returns:
        Credential dict with ``"token"`` key.

    Raises:
        TCBSAuthHandlerError: If login fails or OTP is required but not provided.
        TCBSOTPRequired: If the server requires OTP and none was provided.
            The caller should prompt for OTP and re-call with ``otp=...``.
    """
    if not username:
        raise TCBSAuthHandlerError("TCBS login requires a username.")
    if not password:
        raise TCBSAuthHandlerError("TCBS login requires a password.")

    auth = TCBSAuth(timeout=timeout)

    try:
        token = auth.login(username=username, password=password, otp=otp)
    except TCBSOTPRequired:
        # Re-raise so CLI can prompt for OTP
        raise
    except TCBSAuthError as exc:
        # Wrap in safe handler error — do not expose raw exception detail
        raise TCBSAuthHandlerError(
            "TCBS authentication failed. "
            "Check your username and password and try again."
        ) from exc

    return {
        "token": token,
        "_source": "tcbs_interactive",
        "_provider": "tcbs",
    }


def tcbs_otp_login_handler(
    provider: str,
    username: str = "",
    password: str = "",
    otp_session: str = "",
    otp: str = "",
    timeout: int = 15,
    **kwargs: Any,
) -> dict[str, Any]:
    """AuthManager login handler for TCBS OTP confirmation step.

    Used when the initial login returned a TCBSOTPRequired exception.
    The caller obtains the otp_session from the exception and the otp
    from interactive user input, then calls this handler.

    Args:
        provider: Must be ``"tcbs"`` (case-insensitive).
        username: TCBS account ID.
        password: Account password (used for fallback re-login if needed).
        otp_session: The OTP session from TCBSOTPRequired.
        otp: 6-digit OTP code from TCInvest app.
        timeout: HTTP timeout seconds.
        **kwargs: Ignored.

    Returns:
        Credential dict with ``"token"`` key.

    Raises:
        TCBSAuthHandlerError: If OTP confirmation fails.
    """
    if not otp_session:
        raise TCBSAuthHandlerError("otp_session is required for OTP confirmation.")
    if not otp:
        raise TCBSAuthHandlerError("otp code is required for OTP confirmation.")

    auth = TCBSAuth(timeout=timeout)

    try:
        token = auth.confirm_otp(otp_session=otp_session, otp=otp)
    except TCBSAuthError as exc:
        raise TCBSAuthHandlerError(
            "TCBS OTP confirmation failed. Check your OTP code and try again."
        ) from exc

    return {
        "token": token,
        "_source": "tcbs_interactive",
        "_provider": "tcbs",
    }
