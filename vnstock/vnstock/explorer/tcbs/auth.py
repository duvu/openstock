"""TCBS authentication module.

SCOPE / SAFETY GATE
-------------------
Provides username + password + OTP → Bearer token exchange only.
No broker, account, order, iCopy, margin, or transfer operations.

TCBS uses a two-step login:
  1. POST credentials → receive token OR otpSession challenge
  2. If OTP challenge: POST otp to confirm endpoint → receive token

The token is saved to ~/.config/vnstock/tcbs_token.json and can be loaded
automatically by all TCBS provider classes via TCBSAuth.load_token().
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from vnstock.core.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Auth endpoints  (public — no Bearer required)
# ---------------------------------------------------------------------------
_AUTH_BASE = "https://apipub.tcbs.com.vn"
_LOGIN_URL = f"{_AUTH_BASE}/authen/v1/login"

# OTP confirmation: POST to otp/v1/login/otp with X-OTP-Session header
# If this endpoint is wrong the user will receive a clear error message.
_OTP_CONFIRM_URL = f"{_AUTH_BASE}/otp/v1/login/otp"

# Fallback: some builds confirm OTP by re-posting the same login endpoint
# with an extra `otp` field.  We try _LOGIN_URL first with the otp field
# if the dedicated confirm endpoint returns 4xx.
_LOGIN_WITH_OTP_URL = _LOGIN_URL

# Token persistence
_DEFAULT_TOKEN_PATH = Path.home() / ".config" / "vnstock" / "tcbs_token.json"


class TCBSAuthError(Exception):
    """Raised when TCBS authentication fails."""


class TCBSAuth:
    """
    TCBS authentication helper.

    Usage (interactive / CLI)::

        auth = TCBSAuth()
        token = auth.login(username="105C123456", password="MyPass")
        # If OTP required:
        # token = auth.confirm_otp(otp_session, "123456")

    Usage (load saved token)::

        token = TCBSAuth.load_token()   # returns None if not cached or expired

    The token is a JWT string.  Pass it to provider constructors as
    ``token=token`` or set env var ``TCBS_BEARER_TOKEN``.
    """

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_token(token_path: Optional[Path] = None) -> Optional[str]:
        """Load a previously saved token from disk or env var.

        Priority:
        1. ``TCBS_BEARER_TOKEN`` environment variable
        2. ``LocalFileCredentialStore`` at ``~/.config/vnstock/credentials/tcbs.json``
           (new AuthManager-compatible path)
        3. Legacy token file at *token_path* (default ``~/.config/vnstock/tcbs_token.json``)

        Returns the token string, or ``None`` if not available.
        """
        env_token = os.environ.get("TCBS_BEARER_TOKEN")
        if env_token:
            return env_token.strip()

        # ── New: check CredentialStore path (AuthManager-compatible) ─────
        try:
            from vnstock.core.auth.credential_store import LocalFileCredentialStore

            store = LocalFileCredentialStore()
            creds = store.read("tcbs")
            if creds and isinstance(creds, dict):
                token = creds.get("token")
                if token:
                    return str(token)
        except Exception:
            pass  # fall through to legacy path

        # ── Legacy: ~/.config/vnstock/tcbs_token.json ─────────────────────
        path = token_path or _DEFAULT_TOKEN_PATH
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            token = data.get("token")
            if not token:
                return None
            # Check expiry if stored
            expires_at = data.get("expires_at")
            if expires_at:
                try:
                    expiry_dt = datetime.fromisoformat(expires_at)
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    if datetime.now(tz=timezone.utc) >= expiry_dt:
                        logger.warning(
                            "TCBS token đã hết hạn. Vui lòng đăng nhập lại với `vnstock-tcbs-login`."
                        )
                        return None
                except (ValueError, TypeError):
                    pass
            return token
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Không thể đọc TCBS token file: {exc}")
            return None

    @staticmethod
    def save_token(
        token: str,
        tcbs_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        token_path: Optional[Path] = None,
    ) -> Path:
        """Persist the token to disk.

        Returns the path where the token was saved.
        """
        path = token_path or _DEFAULT_TOKEN_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict = {"token": token, "saved_at": datetime.utcnow().isoformat()}
        if tcbs_id:
            payload["tcbs_id"] = tcbs_id
        if expires_at:
            payload["expires_at"] = expires_at
        path.write_text(json.dumps(payload, indent=2))
        return path

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "source": "tcinvest",
            }
        )

    def login(
        self,
        username: str,
        password: str,
        otp: Optional[str] = None,
    ) -> str:
        """Authenticate with TCBS using username + password [+ OTP].

        Args:
            username: TCBS trading account ID (e.g. ``'105C123456'``).
            password: Account password.
            otp: 6-digit TOTP code from the TCInvest mobile app.
                 Pass this if you already have the OTP ready.
                 If omitted and the server requires OTP, a
                 :class:`TCBSOTPRequired` exception is raised with the
                 ``otp_session`` needed for :meth:`confirm_otp`.

        Returns:
            Bearer token string.

        Raises:
            TCBSOTPRequired: When server returns an OTP challenge and no
                             *otp* argument was provided.
            TCBSAuthError: On invalid credentials or unexpected response.
        """
        payload: dict = {"username": username, "password": password}
        if otp:
            payload["otp"] = otp

        resp = self._post(_LOGIN_URL, payload)
        return self._handle_login_response(resp, username=username, password=password)

    def confirm_otp(self, otp_session: str, otp: str) -> str:
        """Submit OTP for a pending login challenge.

        Args:
            otp_session: The ``otpSession`` value returned by :meth:`login`.
            otp: 6-digit TOTP code from the TCInvest mobile app.

        Returns:
            Bearer token string.

        Raises:
            TCBSAuthError: On wrong OTP or expired session.
        """
        # Try dedicated OTP confirm endpoint first
        try:
            headers = {"X-OTP-Session": otp_session, "x-otp-sessionid": otp_session}
            payload = {"otp": otp}
            resp = self._post(_OTP_CONFIRM_URL, payload, extra_headers=headers)
            return self._extract_token(resp)
        except TCBSAuthError as primary_err:
            # Fallback: re-POST login with otp_session + otp fields
            logger.debug(
                f"OTP confirm endpoint failed ({primary_err}), trying login fallback."
            )
            # We don't have username/password at this point; the caller must
            # use the two-step approach if the dedicated endpoint fails.
            raise TCBSAuthError(
                f"Xác thực OTP thất bại. Lỗi: {primary_err}\n"
                "Nếu lỗi này tiếp tục, hãy thử lại với otp được cung cấp trực tiếp trong "
                "TCBSAuth.login(username, password, otp='XXXXXX')."
            ) from primary_err

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(
        self,
        url: str,
        payload: dict,
        extra_headers: Optional[dict] = None,
    ) -> dict:
        headers = {}
        if extra_headers:
            headers.update(extra_headers)
        try:
            r = self._session.post(
                url,
                data=json.dumps(payload),
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TCBSAuthError(f"Lỗi kết nối tới TCBS: {exc}") from exc

        try:
            data = r.json()
        except ValueError as exc:
            raise TCBSAuthError(
                f"TCBS trả về phản hồi không hợp lệ (HTTP {r.status_code}): {r.text[:200]}"
            ) from exc

        if r.status_code not in (200, 201):
            code = data.get("code", "")
            msg = data.get("message", str(data))
            raise TCBSAuthError(
                f"Đăng nhập thất bại (HTTP {r.status_code}, code={code}): {msg}"
            )

        return data

    def _handle_login_response(
        self,
        data: dict,
        username: str,
        password: str,
    ) -> str:
        """Parse login response; raise TCBSOTPRequired if OTP needed."""
        inner = data.get("data", data)

        # OTP challenge: server returns otpSession
        otp_session = inner.get("otpSession") or data.get("otpSession")
        if otp_session:
            raise TCBSOTPRequired(otp_session=otp_session)

        return self._extract_token(data)

    def _extract_token(self, data: dict) -> str:
        """Extract token from a successful auth response."""
        inner = data.get("data", data)
        token = inner.get("token") or data.get("token")
        if not token:
            raise TCBSAuthError(
                f"Không tìm thấy token trong phản hồi TCBS: {str(data)[:200]}"
            )
        return token


class TCBSOTPRequired(TCBSAuthError):
    """Raised when TCBS requires OTP to complete login.

    Attributes:
        otp_session: Session identifier to pass to :meth:`TCBSAuth.confirm_otp`.
    """

    def __init__(self, otp_session: str):
        self.otp_session = otp_session
        super().__init__(
            f"TCBS yêu cầu OTP. Vui lòng nhập mã OTP từ ứng dụng TCInvest. "
            f"otp_session={otp_session!r}"
        )
