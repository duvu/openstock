"""Natural-language chat execution and rendering for the TUI router."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import anyio

from vnalpha.tui.routing import events

if TYPE_CHECKING:
    from vnalpha.tui.routing.router import TuiInputRouter


class ChatPath:
    """Dispatch chat turns while preserving workspace context semantics."""

    async def route(self, router: TuiInputRouter, raw: str) -> None:
        router._emit_routed("chat", raw)
        router._set_status_chat()
        try:
            if router._chat_controller is None:
                router._output.show_error(
                    "ChatController unavailable.", source="router"
                )
                router._set_status_error("ChatController unavailable")
                return
            from vnalpha.workspace_context.integration import (
                build_workspace_context_prompt_prefix,
            )

            workspace_prefix = build_workspace_context_prompt_prefix(
                router._workspace.workspace_id
            )
            handle_turn = partial(
                router._chat_controller.handle_turn,
                raw,
                workspace_context=workspace_prefix,
            )
            await anyio.to_thread.run_sync(handle_turn)
            router._set_status_ready()
        except Exception as exc:
            public_message = "Assistant request failed unexpectedly. Inspect the debug logs for details."
            router._output.show_error(public_message, source="chat")
            router._set_status_error(public_message)
            events.capture_render_error(exc)
