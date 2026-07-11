"""Deterministic slash-command parser for research workspace commands."""

from __future__ import annotations

import re
import shlex
from typing import Final, Literal

from vnalpha.commands.errors import CommandParseError
from vnalpha.commands.grammar import COMMAND_NAME_RE, OPTION_PREFIX
from vnalpha.commands.models import CommandFilter, ParsedCommand

_FILTER_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(not_contains|contains|!=|>=|<=|>|<|=)"
    r"\s*(.+)$"
)

_CONTEXT_ALIASES: Final[dict[str, str]] = {
    "clean": "clean",
    "compact": "compact",
    "new": "new",
    "resume": "resume",
    "status": "status",
}
_MODEL_ALIASES: Final[dict[str, str]] = {"models": "profiles"}


def parse(text: str) -> ParsedCommand:
    """Parse a slash-command string into a ParsedCommand.

    Raises CommandParseError on any syntax violation.

    Grammar:
        COMMAND   := "/" NAME [ARGUMENTS]
        NAME      := [a-z][a-z0-9_-]*
        ARGUMENTS := POSITIONAL* FILTER* OPTION*
        FILTER    := KEY OP VALUE
        OPTION    := "--" KEY [VALUE]
    """
    raw = text.strip()
    if not raw.startswith("/"):
        raise CommandParseError(f"Commands must start with '/'. Got: {raw!r}")

    try:
        tokens = shlex.split(raw[1:])
    except ValueError as exc:
        raise CommandParseError(f"Unmatched quotes in command: {raw!r}") from exc

    if not tokens:
        raise CommandParseError("Empty command (just '/').")

    name = tokens[0].lower()
    if not COMMAND_NAME_RE.match(name):
        raise CommandParseError(
            f"Invalid command name: {name!r}. "
            "Must start with a letter and contain only [a-z0-9_-]."
        )

    context_subcommand = _CONTEXT_ALIASES.get(name)
    model_subcommand = _MODEL_ALIASES.get(name)
    if context_subcommand:
        command_name = "context"
        positional: list[str] = [context_subcommand]
    elif model_subcommand:
        command_name = "model"
        positional = [model_subcommand]
    else:
        command_name = name
        positional = []
    filters: list[CommandFilter] = []
    options: dict[str, str | bool] = {}

    index = 1
    while index < len(tokens):
        token = tokens[index]

        if token.startswith(OPTION_PREFIX):
            key = token[len(OPTION_PREFIX) :]
            if not key:
                raise CommandParseError("Bare '--' is not a valid option.")
            if index + 1 < len(tokens) and not tokens[index + 1].startswith(
                OPTION_PREFIX
            ):
                next_token = tokens[index + 1]
                if _FILTER_RE.match(next_token) is None:
                    options[key] = next_token
                    index += 2
                    continue
            options[key] = True
            index += 1
            continue

        match = _FILTER_RE.match(token)
        if match:
            filter_key, filter_op, filter_value = (
                match.group(1),
                match.group(2),
                match.group(3),
            )
            filter_value = filter_value.strip()
            if filter_value.startswith((">", "<", "=", "!")):
                raise CommandParseError(
                    f"Malformed filter expression: {token!r}"
                )
            filters.append(
                CommandFilter(
                    key=filter_key,
                    op=_validate_op(filter_op),
                    value=filter_value,
                )
            )
            index += 1
            continue

        positional.append(token)
        index += 1

    return ParsedCommand(
        command_name=command_name,
        raw_text=raw,
        positional=positional,
        filters=filters,
        options=options,
    )


def _validate_op(
    op: str,
) -> Literal["=", "!=", ">", ">=", "<", "<=", "contains", "not_contains"]:
    valid = {"=", "!=", ">", ">=", "<", "<=", "contains", "not_contains"}
    if op not in valid:
        raise CommandParseError(f"Invalid filter operator: {op!r}")
    return op  # type: ignore[return-value]
