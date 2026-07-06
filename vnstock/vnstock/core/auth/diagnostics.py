"""Safe diagnostics metadata model for auth state.

Provides a dataclass that carries safe (non-sensitive) auth metadata
suitable for attachment to DataResult.diagnostics or DataFrame.attrs.

Usage::

    from vnstock.core.auth.diagnostics import AuthDiagnostics

    diag = AuthDiagnostics(
        provider="TCBS",
        auth_used=True,
        auth_type="interactive",
        credential_label="tcbs:local_file",
        experimental=True,
    )
    d = diag.to_dict()
    # Use in DataResult.diagnostics["auth"] = d
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass
class AuthDiagnostics:
    """Safe auth metadata for DataResult and DataFrame.attrs.

    All fields are non-sensitive. Never include tokens, passwords,
    or raw credential material in this object.

    Attributes:
        provider: Provider name.
        auth_used: Whether authentication was used for this request.
        auth_type: String representation of the auth type used.
        credential_label: Non-sensitive credential identifier.
        scopes: Data-read scopes granted.
        expires_at: Token expiry (ISO string) if known.
        experimental: Whether the auth mode is experimental.
        explicit_only: Whether this provider was explicitly requested.
    """

    provider: str = ""
    auth_used: bool = False
    auth_type: str = "none"
    credential_label: str = ""
    scopes: list[str] | None = None
    expires_at: str | None = None
    experimental: bool = False
    explicit_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation safe for diagnostics."""
        d = asdict(self)
        if self.scopes is None:
            d["scopes"] = []
        return d

    @classmethod
    def unauthenticated(cls, provider: str) -> "AuthDiagnostics":
        """Return a safe no-auth diagnostics record."""
        return cls(provider=provider, auth_used=False, auth_type="none")

    @classmethod
    def from_context(cls, ctx: Any) -> "AuthDiagnostics":
        """Build from an :class:`~vnstock.core.auth.context.AuthContext`.

        Args:
            ctx: An ``AuthContext`` instance.

        Returns:
            ``AuthDiagnostics`` with safe fields populated.
        """
        expires_str: str | None = None
        if ctx.expires_at is not None:
            if isinstance(ctx.expires_at, datetime):
                expires_str = ctx.expires_at.isoformat()
            else:
                expires_str = str(ctx.expires_at)

        return cls(
            provider=ctx.provider,
            auth_used=ctx.authenticated,
            auth_type=ctx.auth_type.value
            if hasattr(ctx.auth_type, "value")
            else str(ctx.auth_type),
            credential_label=ctx.credential_label,
            scopes=list(ctx.scopes) if ctx.scopes else [],
            expires_at=expires_str,
            experimental=ctx.experimental,
            explicit_only=ctx.explicit_only,
        )
