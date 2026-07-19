from __future__ import annotations

from rich.text import Text

from vnalpha.core.text_safety import sanitize_text


def capture_tui_exception(exc: Exception) -> None:
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass


def literal_text(value: object, *, style: str | None = None) -> Text:
    return Text(sanitize_text(value), style=style)


def generic_load_error(subject: str) -> Text:
    return Text(f"{subject} is unavailable. Check logs and retry.", style="red")
