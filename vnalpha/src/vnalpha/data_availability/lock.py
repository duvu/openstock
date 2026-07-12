"""Atomic owner-aware lock for data-ensure flows."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import quote
from uuid import uuid4

from vnalpha.core.logging import get_logger

logger = get_logger("data_availability.lock")

_DEFAULT_LOCK_DIR = (
    Path(
        os.getenv(
            "VNALPHA_LOG_PATH",
            str(Path.home() / ".local" / "share" / "openstock" / "logs"),
        )
    ).parent
    / "locks"
)
_STALE_THRESHOLD_SECONDS = 300


class EnsureLockContentionError(RuntimeError):
    def __init__(self, symbol: str, target_date: str) -> None:
        self.symbol = symbol
        self.target_date = target_date
        super().__init__(symbol, target_date)

    def __str__(self) -> str:
        return f"An ensure flow is already active for {self.symbol}/{self.target_date}."


@dataclass(frozen=True, slots=True)
class EnsureLockMetadata:
    symbol: str
    target_date: str
    owner_token: str
    pid: int
    hostname: str
    created_at: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "symbol": self.symbol,
            "target_date": self.target_date,
            "owner_token": self.owner_token,
            "pid": self.pid,
            "hostname": self.hostname,
            "created_at": self.created_at,
        }


def read_lock_metadata(path: Path) -> EnsureLockMetadata | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return EnsureLockMetadata(
            symbol=str(payload["symbol"]),
            target_date=str(payload["target_date"]),
            owner_token=str(payload["owner_token"]),
            pid=int(payload["pid"]),
            hostname=str(payload["hostname"]),
            created_at=str(payload["created_at"]),
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


@contextmanager
def _metadata_guard(path: Path) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _create_lock(path: Path, metadata: EnsureLockMetadata) -> bool:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(metadata.to_dict(), handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _is_stale(path: Path, stale_seconds: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime >= max(stale_seconds, 0.0)
    except FileNotFoundError:
        return False


class EnsureLock:
    """Own one symbol/date provisioning lock until explicit release."""

    def __init__(
        self,
        symbol: str,
        target_date: str,
        *,
        lock_dir: Path | None = None,
        stale_seconds: float = _STALE_THRESHOLD_SECONDS,
    ) -> None:
        normalized_symbol = symbol.upper().strip()
        lock_symbol = quote(normalized_symbol, safe="")
        lock_date = quote(target_date, safe="")
        self._symbol = normalized_symbol
        self._target_date = target_date
        self._lock_dir = lock_dir or _DEFAULT_LOCK_DIR
        self._stale_seconds = stale_seconds
        self._lock_path = self._lock_dir / f"data-ensure-{lock_symbol}-{lock_date}.lock"
        self._guard_path = self._lock_path.with_suffix(".guard")
        self._metadata = EnsureLockMetadata(
            symbol=normalized_symbol,
            target_date=target_date,
            owner_token=uuid4().hex,
            pid=os.getpid(),
            hostname=socket.gethostname(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._acquired = False

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def owner_token(self) -> str:
        return self._metadata.owner_token

    def acquire(self) -> bool:
        """Atomically acquire the lock or report live-owner contention."""

        self._lock_dir.mkdir(parents=True, exist_ok=True)
        with _metadata_guard(self._guard_path):
            if _create_lock(self._lock_path, self._metadata):
                self._acquired = True
                return True
            if not _is_stale(self._lock_path, self._stale_seconds):
                return False

            stale_path: Path | None = self._lock_path.with_name(
                f".{self._lock_path.name}.stale-{uuid4().hex}"
            )
            try:
                os.replace(self._lock_path, stale_path)
            except FileNotFoundError:
                stale_path = None
            acquired = _create_lock(self._lock_path, self._metadata)
            if stale_path is not None:
                stale_path.unlink(missing_ok=True)
            self._acquired = acquired
            return acquired

    def release(self) -> None:
        """Release only when the persisted owner token still matches this owner."""

        if not self._acquired:
            return
        with _metadata_guard(self._guard_path):
            metadata = read_lock_metadata(self._lock_path)
            if metadata is not None and metadata.owner_token == self.owner_token:
                self._lock_path.unlink(missing_ok=True)
        self._acquired = False

    def __enter__(self) -> EnsureLock:
        if not self.acquire():
            raise EnsureLockContentionError(self._symbol, self._target_date)
        return self

    def __exit__(self, *_exc: BaseException | None) -> None:
        self.release()


__all__ = [
    "EnsureLock",
    "EnsureLockContentionError",
    "EnsureLockMetadata",
    "read_lock_metadata",
]
