from __future__ import annotations

from vnalpha.commands.models import ParsedCommand


def accepts_default_date(parsed: ParsedCommand) -> bool:
    if parsed.command_name == "data":
        return (
            len(parsed.positional) >= 2
            and parsed.positional[0] == "build"
            and parsed.positional[1]
            in {"features", "score", "market-regime", "sector-strength"}
        )
    return parsed.command_name not in {"market-regime", "sector-strength"}
