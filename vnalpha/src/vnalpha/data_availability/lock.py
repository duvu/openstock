"""File-based lock for data-ensure flows — prevents duplicate provisioning."""

from __future__ import annotations

import os
import time
from pathlib import Path

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

# A lock older than this many seconds is considered stale.
_STALE_THRESHOLD_SECONDS = 300  # 5 minutes


class EnsureLock:
    """Context-manager lock for a symbol+date ensure flow.

    Uses a simple file lock:
      <lock_dir>/data-ensure-<symbol>-<date>.lock

    If the lock file exists and is fresh, the caller should treat the data as
    already being provisioned (return PARTIAL with retry message).
    If stale, the lock is replaced.
    Lock is always released in __exit__ (finally semantics).
    """

    def __init__(
        self,
        symbol: str,
        target_date: str,
        *,
        lock_dir: Path | None = None,
        stale_seconds: int = _STALE_THRESHOLD_SECONDS,
    ) -> None:
        self._symbol = symbol.upper().strip()
        self._target_date = target_date
        self._lock_dir = lock_dir or _DEFAULT_LOCK_DIR
        self._stale_seconds = stale_seconds
        self._lock_path = (
            self._lock_dir / f"data-ensure-{self._symbol}-{self._target_date}.lock"
        )
        self._acquired = False

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def acquire(self) -> bool:
        """Attempt to acquire the lock.

        Returns True if the lock was acquired (proceed with ensure).
        Returns False if another process holds a fresh lock (skip ensure).
        """
        self._lock_dir.mkdir(parents=True, exist_ok=True)

        if self._lock_path.exists():
            try:
                mtime = self._lock_path.stat().st_mtime
                age = time.time() - mtime
                if age < self._stale_seconds:
                    # Fresh lock held by another flow
                    logger.info(
                        "Lock held for %s/%s (age=%.1fs), skipping ensure",
                        self._symbol,
                        self._target_date,
                        age,
                    )
                    return False
                # Stale lock — replace it
                logger.info(
                    "Stale lock for %s/%s (age=%.1fs > %ds), replacing",
                    self._symbol,
                    self._target_date,
                    age,
                    self._stale_seconds,
                )
            except OSError:
                # File disappeared between exists() and stat() — proceed
                pass

        # Write lock file with our PID
        try:
            self._lock_path.write_text(f"{os.getpid()}\n")
            self._acquired = True
            return True
        except OSError as exc:
            logger.warning(
                "Failed to acquire lock for %s/%s: %s",
                self._symbol,
                self._target_date,
                exc,
            )
            return False

    def release(self) -> None:
        """Release the lock (delete the file). Safe to call multiple times."""
        if self._acquired:
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._acquired = False

    def __enter__(self) -> "EnsureLock":
        self.acquire()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()
