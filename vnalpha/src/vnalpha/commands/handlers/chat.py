from __future__ import annotations

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand


def handle_chat(parsed: ParsedCommand, **kwargs) -> CommandResult:
    subcommand = parsed.positional[0].lower() if parsed.positional else ""
    if subcommand != "new":
        raise CommandValidationError("Unsupported /chat subcommand. Supported: new.")

    conn = kwargs.get("conn")
    if conn is None:
        raise CommandValidationError("chat command requires an active connection.")

    from vnalpha.warehouse.chat_repo import create_chat_session

    target_date = (
        parsed.options.get("date")
        if isinstance(parsed.options.get("date"), str)
        else None
    )
    chat_session_id = create_chat_session(
        conn,
        surface=kwargs.get("surface", "tui-chat"),
        target_date=target_date,
    )
    return CommandResult(
        status="SUCCESS",
        title="/chat new",
        summary=f"New chat session started. (id={chat_session_id[:8]}…)",
        metadata={"chat_session_id": chat_session_id},
    )
