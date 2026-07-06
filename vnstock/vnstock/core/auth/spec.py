"""Auth spec model — describes authentication requirements for a provider/dataset."""

from __future__ import annotations

from dataclasses import dataclass, field

from vnstock.core.auth.types import AuthType


@dataclass(frozen=True)
class AuthSpec:
    """Describes the authentication requirements for a provider dataset.

    Attributes:
        auth_type: The :class:`AuthType` required.
        required: If ``True``, auth is required; if ``False``, optional or absent.
        experimental: If ``True``, treat this auth mode as experimental.
        explicit_only: If ``True``, auth is only used when caller explicitly
            selects this provider (not included in auto-routing).
        scopes: Optional list of data-read scopes this auth grants.
        notes: Optional human-readable notes about this auth spec.

    Examples::

        # Public provider — no auth
        AuthSpec(auth_type=AuthType.NONE, required=False)

        # TCBS — interactive login, experimental, explicit-only
        AuthSpec(
            auth_type=AuthType.INTERACTIVE,
            required=True,
            experimental=True,
            explicit_only=True,
            scopes=["equity.ohlcv", "equity.quote"],
            notes="TCBS login via username+password+OTP. Data-read only.",
        )
    """

    auth_type: AuthType = AuthType.NONE
    required: bool = False
    experimental: bool = False
    explicit_only: bool = False
    scopes: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    @classmethod
    def no_auth(cls) -> "AuthSpec":
        """Return a no-auth spec for public providers."""
        return cls(auth_type=AuthType.NONE, required=False)

    @classmethod
    def tcbs_experimental(cls, scopes: tuple[str, ...] = ()) -> "AuthSpec":
        """Return the TCBS experimental auth spec (interactive, explicit-only)."""
        return cls(
            auth_type=AuthType.INTERACTIVE,
            required=True,
            experimental=True,
            explicit_only=True,
            scopes=scopes,
            notes=(
                "TCBS interactive login (username+password+OTP). "
                "Experimental and data-read only. "
                "Use `vnstock auth login tcbs` to authenticate."
            ),
        )
