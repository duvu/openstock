from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Final

_NETWORK_BLOCKED: Final[ContextVar[bool]] = ContextVar(
    "vnalpha_runtime_replay_network_blocked", default=False
)


@dataclass(frozen=True, slots=True)
class NetworkAccessProhibitedError(RuntimeError):
    event: str

    def __str__(self) -> str:
        return f"runtime replay prohibits network access: {self.event}"


def _network_audit_hook(event: str, _arguments) -> None:
    if _NETWORK_BLOCKED.get() and event.startswith("socket."):
        raise NetworkAccessProhibitedError(event=event)


sys.addaudithook(_network_audit_hook)


@contextmanager
def prohibit_network() -> Iterator[None]:
    token = _NETWORK_BLOCKED.set(True)
    try:
        yield
    finally:
        _NETWORK_BLOCKED.reset(token)
