from __future__ import annotations

from collections.abc import Collection

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import ParsedCommand


def validate_command_input(
    parsed: ParsedCommand,
    allowed_options: Collection[str],
    maximum_positionals: int,
) -> None:
    if parsed.filters:
        raise CommandValidationError("Filters are not supported by this command.")
    if len(parsed.positional) > maximum_positionals:
        raise CommandValidationError("Too many positional arguments for this command.")
    unsupported_options = set(parsed.options) - set(allowed_options)
    if unsupported_options:
        options = ", ".join(sorted(f"--{option}" for option in unsupported_options))
        raise CommandValidationError(f"Unsupported option: {options}.")
