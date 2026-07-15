from __future__ import annotations

import hashlib
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Iterator, Protocol

import pandas as pd

from vnstock.providers.fiinquantx.approval import fiinquantx_license_approval
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXAuthenticationError,
    FiinQuantXConcurrencyError,
    FiinQuantXCredentialsMissingError,
    FiinQuantXLicenseNotAcknowledgedError,
    FiinQuantXProviderError,
    map_fiinquantx_exception,
)


class FiinQuantXTradingEvent(Protocol):
    def get_data(self) -> pd.DataFrame: ...


class FiinQuantXSession(Protocol):
    def Fetch_Trading_Data(
        self,
        **kwargs: str | int | bool | list[str] | None,
    ) -> FiinQuantXTradingEvent: ...

    def TickerList(self, ticker: str) -> list[str]: ...


@dataclass(slots=True)
class _SessionEntry:
    module: ModuleType
    session: FiinQuantXSession
    username_fingerprint: str
    expires_at: float


_MAX_CONCURRENCY = 1
_REQUEST_SEMAPHORE = threading.BoundedSemaphore(_MAX_CONCURRENCY)
_SESSION_LOCK = threading.RLock()
_SESSION_ENTRY: _SessionEntry | None = None
_ACTIVE_REQUESTS = 0


def _parse_positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _username_fingerprint(username: str) -> str:
    return hashlib.sha256(username.encode("utf-8")).hexdigest()[:12]


def _close_session(session: object) -> None:
    for method_name in ("logout", "close", "disconnect"):
        method = getattr(session, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:  # noqa: BLE001 - cleanup is best effort and redacted
                pass
            return


def reset_fiinquantx_runtime_state() -> None:
    """Clear cached session state; intended for tests and controlled shutdown."""

    global _SESSION_ENTRY, _ACTIVE_REQUESTS
    with _SESSION_LOCK:
        if _SESSION_ENTRY is not None:
            _close_session(_SESSION_ENTRY.session)
        _SESSION_ENTRY = None
        _ACTIVE_REQUESTS = 0


class FiinQuantXSessionProvider:
    def get_session(self, module: ModuleType, dataset: str) -> FiinQuantXSession:
        global _SESSION_ENTRY
        if not fiinquantx_license_approval().approved:
            raise FiinQuantXLicenseNotAcknowledgedError(dataset)
        username = os.environ.get("FIINQUANT_USERNAME")
        password = os.environ.get("FIINQUANT_PASSWORD")
        if not username or not password:
            raise FiinQuantXCredentialsMissingError(dataset)

        fingerprint = _username_fingerprint(username)
        now = time.monotonic()
        session_ttl = _parse_positive_float("VNSTOCK_FIINQUANTX_SESSION_TTL", 900.0)
        with _SESSION_LOCK:
            entry = _SESSION_ENTRY
            if (
                entry is not None
                and entry.module is module
                and entry.username_fingerprint == fingerprint
                and entry.expires_at > now
            ):
                return entry.session
            if entry is not None:
                _close_session(entry.session)
                _SESSION_ENTRY = None

            factory = getattr(module, "FiinSession", None)
            if factory is None or not callable(factory):
                raise FiinQuantXAuthenticationError(dataset)
            try:
                session = factory(username=username, password=password).login()
            except Exception as exc:  # noqa: BLE001 - vendor boundary
                raise map_fiinquantx_exception(exc, dataset) from None
            _SESSION_ENTRY = _SessionEntry(
                module=module,
                session=session,
                username_fingerprint=fingerprint,
                expires_at=now + session_ttl,
            )
            return session

    def invalidate(self) -> None:
        global _SESSION_ENTRY
        with _SESSION_LOCK:
            if _SESSION_ENTRY is not None:
                _close_session(_SESSION_ENTRY.session)
            _SESSION_ENTRY = None

    @contextmanager
    def request_session(
        self,
        module: ModuleType,
        dataset: str,
    ) -> Iterator[FiinQuantXSession]:
        global _ACTIVE_REQUESTS
        timeout = _parse_positive_float("VNSTOCK_FIINQUANTX_ACQUIRE_TIMEOUT", 30.0)
        acquired = _REQUEST_SEMAPHORE.acquire(timeout=timeout)
        if not acquired:
            raise FiinQuantXConcurrencyError(dataset)
        with _SESSION_LOCK:
            _ACTIVE_REQUESTS += 1
        try:
            session = self.get_session(module, dataset)
            try:
                yield session
            except FiinQuantXProviderError:
                raise
            except Exception as exc:  # noqa: BLE001 - vendor boundary
                mapped = map_fiinquantx_exception(exc, dataset)
                if isinstance(mapped, FiinQuantXAuthenticationError):
                    self.invalidate()
                raise mapped from None
        finally:
            with _SESSION_LOCK:
                _ACTIVE_REQUESTS = max(0, _ACTIVE_REQUESTS - 1)
            _REQUEST_SEMAPHORE.release()

    def diagnostics(self) -> dict[str, int | float | bool]:
        with _SESSION_LOCK:
            entry = _SESSION_ENTRY
            now = time.monotonic()
            return {
                "max_concurrency": _MAX_CONCURRENCY,
                "active_requests": _ACTIVE_REQUESTS,
                "session_cached": entry is not None and entry.expires_at > now,
                "session_expires_in_seconds": (
                    max(0.0, round(entry.expires_at - now, 3)) if entry else 0.0
                ),
            }


DEFAULT_FIINQUANTX_SESSION_PROVIDER = FiinQuantXSessionProvider()


__all__ = [
    "DEFAULT_FIINQUANTX_SESSION_PROVIDER",
    "FiinQuantXSession",
    "FiinQuantXSessionProvider",
    "FiinQuantXTradingEvent",
    "reset_fiinquantx_runtime_state",
]
