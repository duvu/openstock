"""Auth policy model — routing policy for authenticated vs public providers."""

from __future__ import annotations

from enum import Enum


class AuthPolicy(str, Enum):
    """Routing policy controlling how authenticated providers are selected.

    Attributes:
        FORBID_AUTHENTICATED: Never select authenticated providers.
            Use only public (no-auth) providers.
        PREFER_NO_AUTH: Prefer public providers, fall back to authenticated
            only if no public provider is available.
        ALLOW_AUTHENTICATED: Allow authenticated providers to be selected
            alongside public providers, based on health/priority.
        REQUIRE_AUTHENTICATED: Only select authenticated providers.
            Fail clearly if no authenticated provider has valid auth state.
    """

    FORBID_AUTHENTICATED = "forbid_authenticated"
    PREFER_NO_AUTH = "prefer_no_auth"
    ALLOW_AUTHENTICATED = "allow_authenticated"
    REQUIRE_AUTHENTICATED = "require_authenticated"


#: Default policy for the local data service and SDK usage.
DEFAULT_AUTH_POLICY: AuthPolicy = AuthPolicy.PREFER_NO_AUTH
