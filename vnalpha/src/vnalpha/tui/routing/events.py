"""Observability helpers for TUI routing outcomes."""

from __future__ import annotations


def emit_routed(route_type: str, raw: str) -> None:
    """Emit the existing command or chat routing audit event."""
    del raw
    try:
        from vnalpha.observability.audit import log_audit

        event = "TUI_COMMAND_ROUTED" if route_type == "command" else "TUI_CHAT_ROUTED"
        log_audit(event, f"route_type={route_type}", module="vnalpha.tui.input_router")
    except Exception:
        pass


def emit_rejected(raw: str, reason: str) -> None:
    del raw
    try:
        from vnalpha.observability.audit import log_audit

        log_audit(
            "TUI_INPUT_REJECTED",
            f"reason={reason}",
            module="vnalpha.tui.input_router",
        )
    except Exception:
        pass


def capture_render_error(exc: Exception) -> None:
    """Capture a rendering failure through the existing observability hook."""
    try:
        from vnalpha.observability.errors import capture_exception

        capture_exception(exc)
    except Exception:
        pass
