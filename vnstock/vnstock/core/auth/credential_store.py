"""Credential store abstraction for vnstock auth layer.

Provides:

- :class:`CredentialStore` — abstract interface
- :class:`MemoryCredentialStore` — in-memory store for tests
- :class:`EnvCredentialStore` — environment-variable backed store
- :class:`LocalFileCredentialStore` — restricted-permission local file store
- :class:`KeyringCredentialStore` — system keyring store (where available)
- :class:`VaultCredentialStore` — vault-compatible adapter interface

Usage::

    from vnstock.core.auth.credential_store import MemoryCredentialStore

    store = MemoryCredentialStore()
    store.write("tcbs", {"token": "abc"})
    data = store.read("tcbs")       # {"token": "abc"}
    store.delete("tcbs")
    store.read("tcbs")              # None
"""

from __future__ import annotations

import json
import os
import stat
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class CredentialStore(ABC):
    """Abstract credential store interface.

    All implementations must support read/write/delete/has operations.
    Credential material is stored as plain dicts.

    Implementations MUST NOT log or print credential material.
    """

    @abstractmethod
    def read(self, provider: str) -> Optional[dict[str, Any]]:
        """Read stored credentials for *provider*.

        Args:
            provider: Provider name key (e.g., ``"tcbs"``).

        Returns:
            Credential dict, or ``None`` if not stored.
        """
        ...

    @abstractmethod
    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        """Write credentials for *provider*.

        Args:
            provider: Provider name key.
            credentials: Dict of credential material to store.
        """
        ...

    @abstractmethod
    def delete(self, provider: str) -> None:
        """Delete stored credentials for *provider*.

        Args:
            provider: Provider name key.

        No-op if no credentials exist for *provider*.
        """
        ...

    def has(self, provider: str) -> bool:
        """Return whether credentials exist for *provider*.

        Args:
            provider: Provider name key.

        Returns:
            ``True`` if credentials are stored and non-None.
        """
        return self.read(provider) is not None

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        """Return safe (non-sensitive) diagnostics for *provider* credentials.

        Implementations may override to return richer metadata.

        Args:
            provider: Provider name key.

        Returns:
            Dict with safe metadata (e.g., ``{"stored": True, "source": "memory"}``).
        """
        return {"stored": self.has(provider), "source": self.__class__.__name__}


# ---------------------------------------------------------------------------
# Memory store — for tests
# ---------------------------------------------------------------------------


class MemoryCredentialStore(CredentialStore):
    """Thread-safe in-memory credential store, primarily for tests.

    Data does not persist across process restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    def read(self, provider: str) -> Optional[dict[str, Any]]:
        with self._lock:
            entry = self._data.get(provider)
            return dict(entry) if entry is not None else None

    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        with self._lock:
            self._data[provider] = dict(credentials)

    def delete(self, provider: str) -> None:
        with self._lock:
            self._data.pop(provider, None)

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        return {"stored": self.has(provider), "source": "memory"}


# ---------------------------------------------------------------------------
# Environment-backed store — for controlled development use
# ---------------------------------------------------------------------------


class EnvCredentialStore(CredentialStore):
    """Credential store backed by environment variables.

    Reads credentials from env vars using a naming convention:
    ``VNSTOCK_<PROVIDER>_<KEY>`` (e.g., ``VNSTOCK_TCBS_TOKEN``).

    Write/delete operations are no-ops on env stores (env vars are
    set externally). ``has()`` checks if the expected variable is set.

    This store is intended for CI/CD and controlled development usage.
    It supports single-key credentials (e.g., bearer tokens).

    The env var name prefix can be customized via *prefix*.
    """

    def __init__(self, prefix: str = "VNSTOCK") -> None:
        self._prefix = prefix.upper().rstrip("_")

    def _env_key(self, provider: str, field: str = "TOKEN") -> str:
        return f"{self._prefix}_{provider.upper()}_{field.upper()}"

    def read(self, provider: str) -> Optional[dict[str, Any]]:
        """Read token from ``VNSTOCK_<PROVIDER>_TOKEN`` env var."""
        key = self._env_key(provider, "TOKEN")
        token = os.environ.get(key)
        if token:
            return {"token": token.strip(), "_source": "env", "_env_key": key}
        return None

    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        """No-op: env vars are set externally."""

    def delete(self, provider: str) -> None:
        """No-op: env vars are managed externally."""

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        key = self._env_key(provider, "TOKEN")
        return {
            "stored": os.environ.get(key) is not None,
            "source": "env",
            "env_key": key,
        }


# ---------------------------------------------------------------------------
# Local file store — restricted permissions
# ---------------------------------------------------------------------------

_DEFAULT_CRED_DIR = Path.home() / ".config" / "vnstock" / "credentials"
_FILE_MODE = 0o600  # owner read/write only


class LocalFileCredentialStore(CredentialStore):
    """Credential store backed by restricted-permission JSON files.

    Each provider's credentials are stored in a separate JSON file at
    ``<base_dir>/<provider>.json`` with permissions ``600``.

    The directory is created with ``700`` permissions on first write.

    Args:
        base_dir: Base directory for credential files.
                  Defaults to ``~/.config/vnstock/credentials/``.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_CRED_DIR

    def _path(self, provider: str) -> Path:
        return self._base_dir / f"{provider.lower()}.json"

    def _ensure_dir(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # Restrict directory permissions to owner only
        try:
            os.chmod(self._base_dir, 0o700)
        except OSError:
            pass

    def read(self, provider: str) -> Optional[dict[str, Any]]:
        path = self._path(provider)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        self._ensure_dir()
        path = self._path(provider)
        path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        try:
            os.chmod(path, _FILE_MODE)
        except OSError:
            pass

    def delete(self, provider: str) -> None:
        path = self._path(provider)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        path = self._path(provider)
        perms: Optional[str] = None
        if path.exists():
            try:
                mode = stat.S_IMODE(path.stat().st_mode)
                perms = oct(mode)
            except OSError:
                pass
        return {
            "stored": path.exists(),
            "source": "local_file",
            "path": str(path),
            "permissions": perms,
        }


# ---------------------------------------------------------------------------
# Keyring store — system keyring where available
# ---------------------------------------------------------------------------

_KEYRING_SERVICE = "vnstock"


class KeyringCredentialStore(CredentialStore):
    """Credential store backed by the system keyring (where supported).

    Requires ``keyring`` package. Falls back gracefully if not available.

    Each provider token is stored under service ``"vnstock"`` with
    username equal to the provider name.

    Args:
        service: Keyring service name (default ``"vnstock"``).
    """

    def __init__(self, service: str = _KEYRING_SERVICE) -> None:
        self._service = service
        self._available: Optional[bool] = None

    def _check_available(self) -> bool:
        if self._available is None:
            try:
                import keyring  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def read(self, provider: str) -> Optional[dict[str, Any]]:
        if not self._check_available():
            return None
        try:
            import keyring

            token = keyring.get_password(self._service, provider.lower())
            if token:
                return {"token": token, "_source": "keyring"}
            return None
        except Exception:
            return None

    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        if not self._check_available():
            return
        token = credentials.get("token")
        if not token:
            return
        try:
            import keyring

            keyring.set_password(self._service, provider.lower(), str(token))
        except Exception:
            pass

    def delete(self, provider: str) -> None:
        if not self._check_available():
            return
        try:
            import keyring

            keyring.delete_password(self._service, provider.lower())
        except Exception:
            pass

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        return {
            "stored": self.has(provider),
            "source": "keyring",
            "available": self._check_available(),
        }


# ---------------------------------------------------------------------------
# Vault-compatible adapter interface — for future enterprise deployments
# ---------------------------------------------------------------------------


class VaultCredentialStore(CredentialStore):
    """Vault-compatible credential store adapter interface.

    This is a stub/interface for future integration with HashiCorp Vault
    or compatible secret stores. Not implemented in Phase 4.

    Subclass this and override ``read``, ``write``, ``delete`` to integrate
    with a real Vault instance.
    """

    def read(self, provider: str) -> Optional[dict[str, Any]]:
        """Not implemented in Phase 4."""
        raise NotImplementedError(
            "VaultCredentialStore is not implemented. "
            "Subclass and implement read/write/delete for your Vault integration."
        )

    def write(self, provider: str, credentials: dict[str, Any]) -> None:
        """Not implemented in Phase 4."""
        raise NotImplementedError("VaultCredentialStore is not implemented.")

    def delete(self, provider: str) -> None:
        """Not implemented in Phase 4."""
        raise NotImplementedError("VaultCredentialStore is not implemented.")

    def safe_diagnostics(self, provider: str) -> dict[str, Any]:
        return {"stored": False, "source": "vault", "available": False}
