"""Auth type enumeration for vnstock auth layer."""

from __future__ import annotations

from enum import Enum


class AuthType(str, Enum):
    """Enumeration of supported authentication types.

    Attributes:
        NONE: No authentication required or used.
        BEARER_TOKEN: Bearer token (JWT or similar) in Authorization header.
        API_KEY: Static API key passed in header or query parameter.
        BASIC: HTTP Basic auth (username + password).
        OAUTH2: OAuth 2.0 access/refresh token pair.
        INTERACTIVE: Interactive local login (e.g., OTP-based TCBS login).
        CUSTOM: Provider-defined custom auth mechanism.
    """

    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    INTERACTIVE = "interactive"
    CUSTOM = "custom"
