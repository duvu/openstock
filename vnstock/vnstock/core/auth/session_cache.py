"""Session cache abstraction for auth tokens.

Provides an in-memory session cache with TTL-based expiry.
Intended for caching live bearer tokens after login so that
providers do not need to re-read from disk on every request.

Usage::

    from vnstock.core.auth.session_cache import SessionCache

    cache = SessionCache()
    cache.set("tcbs", token, ttl_seconds=3600)
    token = cache.get("tcbs")   # None if expired or missing
    cache.delete("tcbs")
    cache.clear()
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class SessionCache:
    """Thread-safe in-memory session token cache with TTL expiry.

    Entries are invalidated lazily when accessed after expiry.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # provider -> (token, expiry_epoch)
        self._store: dict[str, tuple[str, float]] = {}

    def set(self, provider: str, token: str, ttl_seconds: float = 3600.0) -> None:
        """Cache *token* for *provider* with a TTL.

        Args:
            provider: Provider name key.
            token: Token string to cache.
            ttl_seconds: Time-to-live in seconds (default 1 hour).
        """
        expiry = time.time() + ttl_seconds
        with self._lock:
            self._store[provider] = (token, expiry)

    def get(self, provider: str) -> Optional[str]:
        """Return cached token for *provider*, or ``None`` if missing/expired.

        Args:
            provider: Provider name key.

        Returns:
            Cached token string, or ``None``.
        """
        with self._lock:
            entry = self._store.get(provider)
            if entry is None:
                return None
            token, expiry = entry
            if time.time() >= expiry:
                del self._store[provider]
                return None
            return token

    def delete(self, provider: str) -> None:
        """Remove cached entry for *provider* if present.

        Args:
            provider: Provider name key.
        """
        with self._lock:
            self._store.pop(provider, None)

    def clear(self) -> None:
        """Remove all cached entries."""
        with self._lock:
            self._store.clear()

    def is_cached(self, provider: str) -> bool:
        """Return whether a non-expired entry exists for *provider*.

        Args:
            provider: Provider name key.
        """
        return self.get(provider) is not None
