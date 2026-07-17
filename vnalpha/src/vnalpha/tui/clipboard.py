from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from vnalpha.core.text_safety import sanitize_text

MAX_CLIPBOARD_CHARACTERS = 200_000


class ClipboardError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClipboardReceipt:
    confirmed: bool
    detail: str


class ClipboardPort(Protocol):
    def copy(self, text: str) -> ClipboardReceipt: ...


class TextualClipboardPort:
    def __init__(self, copy_to_clipboard: Callable[[str], None]) -> None:
        self._copy_to_clipboard = copy_to_clipboard

    def copy(self, text: str) -> ClipboardReceipt:
        try:
            self._copy_to_clipboard(text)
        except Exception as exc:
            raise ClipboardError(str(exc) or "terminal clipboard unavailable") from exc
        return ClipboardReceipt(
            confirmed=False,
            detail="terminal confirmation unavailable",
        )


def prepare_clipboard_text(text: str) -> tuple[str, bool]:
    sanitized = sanitize_text(text).strip()
    if len(sanitized) <= MAX_CLIPBOARD_CHARACTERS:
        return sanitized, False
    return sanitized[:MAX_CLIPBOARD_CHARACTERS], True
