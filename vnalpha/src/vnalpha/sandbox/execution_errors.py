from __future__ import annotations


class SandboxExecutionError(ValueError):
    __slots__ = ("_reason",)

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self._reason = reason

    def __str__(self) -> str:
        return self._reason
