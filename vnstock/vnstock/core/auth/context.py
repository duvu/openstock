"""Auth context model — runtime resolved auth state for a provider request."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from vnstock.core.auth.types import AuthType


@dataclass
class AuthContext:
    """Resolved auth context for a provider data request.

    Carries the auth state needed by a provider to make an authenticated
    request, plus safe metadata for diagnostics.

    IMPORTANT: This object MAY hold live credential material in ``_token``
    and ``_credentials`` (underscore-prefixed, not serialized to diagnostics).
    Never log or return these fields to callers.

    Attributes:
        provider: Provider name this context is for.
        auth_type: The auth type in use.
        authenticated: Whether valid auth state is present.
        credential_label: A non-sensitive label identifying the credential
            (e.g., ``"tcbs:local_file"``). Safe for diagnostics.
        scopes: Data-read scopes granted.
        expires_at: Token expiry (UTC) if known.
        experimental: Whether this auth mode is experimental.
        explicit_only: Whether this was explicitly requested.
        _token: Live bearer token string (never expose to callers).
        _credentials: Extra credential material dict (never expose).
    """

    provider: str
    auth_type: AuthType = AuthType.NONE
    authenticated: bool = False
    credential_label: str = ""
    scopes: tuple[str, ...] = field(default_factory=tuple)
    expires_at: datetime | None = None
    experimental: bool = False
    explicit_only: bool = False

    # Private — credential material, never serialize
    _token: str | None = field(default=None, repr=False, compare=False)
    _credentials: dict[str, Any] | None = field(default=None, repr=False, compare=False)

    def safe_diagnostics(self) -> dict[str, Any]:
        """Return safe metadata dict suitable for DataResult.diagnostics.

        Returns only non-sensitive fields. Never includes token or credentials.
        """
        return {
            "provider": self.provider,
            "auth_type": self.auth_type.value,
            "authenticated": self.authenticated,
            "credential_label": self.credential_label,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "experimental": self.experimental,
            "explicit_only": self.explicit_only,
        }

    @classmethod
    def unauthenticated(cls, provider: str) -> "AuthContext":
        """Return an unauthenticated context for *provider*."""
        return cls(provider=provider, auth_type=AuthType.NONE, authenticated=False)
