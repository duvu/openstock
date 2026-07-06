"""AuthManager — centralized authentication manager for vnstock.

Manages provider login/logout flows, auth context resolution,
and credential availability checks.

AuthManager does NOT expose raw credential material to callers.
It returns safe :class:`~vnstock.core.auth.context.AuthContext` objects.

Usage::

    from vnstock.core.auth.manager import AuthManager
    from vnstock.core.auth.credential_store import LocalFileCredentialStore

    manager = AuthManager(store=LocalFileCredentialStore())

    # Check auth status
    status = manager.auth_status("tcbs")
    # -> {"provider": "tcbs", "authenticated": True, ...}

    # Resolve auth context for a request
    ctx = manager.resolve_context("tcbs")
    # -> AuthContext with _token populated (safe to pass to provider)

    # Logout
    manager.logout("tcbs")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from vnstock.core.auth.context import AuthContext
from vnstock.core.auth.credential_store import CredentialStore, MemoryCredentialStore
from vnstock.core.auth.session_cache import SessionCache
from vnstock.core.auth.types import AuthType

if TYPE_CHECKING:
    pass


#: Type alias for provider login callable.
#: Signature: (provider: str, **kwargs) -> dict[str, Any]
LoginCallable = Callable[..., dict[str, Any]]


class AuthManager:
    """Centralized auth manager for provider credentials.

    Manages:
    - Provider login dispatch (via registered login callables)
    - Auth context resolution (reads from credential store + session cache)
    - Logout and credential deletion
    - Auth status queries
    - Credential availability checks

    Raw credential material is never exposed to callers; only safe
    :class:`AuthContext` objects and status dicts are returned.

    Args:
        store: :class:`CredentialStore` implementation to use.
        session_cache: Optional :class:`SessionCache` (defaults to new instance).
    """

    def __init__(
        self,
        store: Optional[CredentialStore] = None,
        session_cache: Optional[SessionCache] = None,
    ) -> None:
        self._store: CredentialStore = store or MemoryCredentialStore()
        self._session_cache: SessionCache = session_cache or SessionCache()
        # provider -> login callable
        self._login_handlers: dict[str, LoginCallable] = {}

    # ------------------------------------------------------------------
    # Login handler registration
    # ------------------------------------------------------------------

    def register_login_handler(self, provider: str, handler: LoginCallable) -> None:
        """Register a login callable for *provider*.

        The handler is called by :meth:`login` when the user requests
        interactive login for *provider*.

        Args:
            provider: Provider name (case-insensitive).
            handler: Callable that accepts ``(provider, **kwargs)`` and returns
                     a credential dict with at least a ``"token"`` key.
        """
        self._login_handlers[provider.lower()] = handler

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    def login(self, provider: str, **kwargs: Any) -> AuthContext:
        """Dispatch interactive login for *provider*.

        Calls the registered login handler, stores resulting credentials
        in the credential store and session cache.

        Args:
            provider: Provider name.
            **kwargs: Provider-specific login arguments (e.g., ``username``,
                      ``password``, ``otp``).

        Returns:
            :class:`AuthContext` for *provider* (authenticated=True on success).

        Raises:
            AuthManagerError: If no login handler is registered for *provider*,
                or if the login callable raises.
        """
        key = provider.lower()
        handler = self._login_handlers.get(key)
        if handler is None:
            raise AuthManagerError(
                f"No login handler registered for provider '{provider}'. "
                "Register one via AuthManager.register_login_handler()."
            )

        credentials = handler(provider=provider, **kwargs)
        if not isinstance(credentials, dict):
            raise AuthManagerError(
                f"Login handler for '{provider}' must return a dict, "
                f"got {type(credentials).__name__}."
            )

        # Persist credentials
        self._store.write(key, credentials)

        # Update session cache
        token = credentials.get("token")
        if token:
            ttl = credentials.get("_ttl_seconds", 3600.0)
            self._session_cache.set(key, str(token), ttl_seconds=float(ttl))

        return self.resolve_context(provider)

    def logout(self, provider: str) -> None:
        """Log out *provider* by clearing session cache (but not stored credentials).

        To fully remove credentials, use :meth:`delete`.

        Args:
            provider: Provider name.
        """
        self._session_cache.delete(provider.lower())

    def delete(self, provider: str) -> None:
        """Delete stored credentials for *provider* and clear session cache.

        Args:
            provider: Provider name.
        """
        key = provider.lower()
        self._session_cache.delete(key)
        self._store.delete(key)

    # ------------------------------------------------------------------
    # Auth context resolution
    # ------------------------------------------------------------------

    def resolve_context(self, provider: str) -> AuthContext:
        """Resolve the current auth context for *provider*.

        Reads from session cache first, then credential store.

        Args:
            provider: Provider name.

        Returns:
            :class:`AuthContext` with ``_token`` populated if authenticated,
            or unauthenticated context if no credentials exist.
        """
        key = provider.lower()

        # Try session cache first
        cached_token = self._session_cache.get(key)
        if cached_token:
            return AuthContext(
                provider=provider,
                auth_type=AuthType.BEARER_TOKEN,
                authenticated=True,
                credential_label=f"{key}:session_cache",
                _token=cached_token,
            )

        # Fall back to credential store
        creds = self._store.read(key)
        if creds is None:
            return AuthContext.unauthenticated(provider)

        token = creds.get("token")
        if not token:
            return AuthContext.unauthenticated(provider)

        # Populate session cache for future requests
        self._session_cache.set(key, str(token), ttl_seconds=3600.0)

        source = creds.get("_source", "store")
        return AuthContext(
            provider=provider,
            auth_type=AuthType.BEARER_TOKEN,
            authenticated=True,
            credential_label=f"{key}:{source}",
            _token=str(token),
            _credentials=None,  # never expose raw creds
        )

    # ------------------------------------------------------------------
    # Auth status
    # ------------------------------------------------------------------

    def auth_status(self, provider: str) -> dict[str, Any]:
        """Return safe auth status dict for *provider*.

        Does NOT include raw credential material.

        Args:
            provider: Provider name.

        Returns:
            Dict with keys: ``provider``, ``authenticated``, ``credential_label``,
            ``source`` (from store diagnostics), ``cached``.
        """
        key = provider.lower()
        ctx = self.resolve_context(provider)
        store_diag = self._store.safe_diagnostics(key)
        return {
            "provider": provider,
            "authenticated": ctx.authenticated,
            "credential_label": ctx.credential_label,
            "cached": self._session_cache.is_cached(key),
            "store": store_diag,
        }

    def auth_status_all(
        self, providers: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return safe auth status for multiple providers.

        Args:
            providers: List of provider names.  When ``None`` (default),
                returns status for the built-in auth-capable providers
                (``tcbs`` and ``fmp``).

        Returns:
            List of status dicts (one per provider).
        """
        if providers is None:
            providers = ["tcbs", "fmp"]
        return [self.auth_status(p) for p in providers]

    # ------------------------------------------------------------------
    # Credential availability
    # ------------------------------------------------------------------

    def has_credentials(self, provider: str) -> bool:
        """Return whether valid credentials exist for *provider*.

        Checks session cache first, then credential store.

        Args:
            provider: Provider name.

        Returns:
            ``True`` if non-expired credentials are available.
        """
        ctx = self.resolve_context(provider)
        return ctx.authenticated


class AuthManagerError(Exception):
    """Raised when AuthManager encounters an unrecoverable error."""
