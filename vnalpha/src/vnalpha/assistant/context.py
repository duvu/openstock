from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnalpha.chat.context import ChatContext


def prefix_assistant_prompt(
    user_prompt: str,
    workspace_context: str | None,
    chat_context: ChatContext | None,
) -> str:
    prefixes: list[str] = []
    if workspace_context:
        prefixes.append(workspace_context)
    if chat_context is not None:
        from vnalpha.chat.context import build_context_prompt_prefix

        chat_prefix = build_context_prompt_prefix(chat_context)
        if chat_prefix:
            prefixes.append(chat_prefix)
    return "".join(prefixes) + user_prompt
