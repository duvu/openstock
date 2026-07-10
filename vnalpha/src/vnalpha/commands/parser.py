"""Deterministic slash-command parser for Phase 5.8."""

from __future__ import annotations

import re
import shlex
from typing import Final, Literal

from vnalpha.commands.errors import CommandParseError
from vnalpha.commands.grammar import COMMAND_NAME_RE, OPTION_PREFIX
from vnalpha.commands.models import CommandFilter, ParsedCommand

# Filter expression pattern: KEY OP VALUE (op before value; op is non-alpha so no space)
# e.g. score>=0.70  class=STRONG_CANDIDATE  risk_flags not_contains THIN_VOLUME
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

    # Split off leading "/" and tokenize respecting quotes
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
    command_name = "context" if context_subcommand else name
    positional: list[str] = [context_subcommand] if context_subcommand else []
    filters: list[CommandFilter] = []
    options: dict[str, str | bool] = {}

    i = 1
    while i < len(tokens):
        tok = tokens[i]

        # Option: --key [value]
        if tok.startswith(OPTION_PREFIX):
            key = tok[len(OPTION_PREFIX) :]
            if not key:
                raise CommandParseError("Bare '--' is not a valid option.")
            # Peek at next token; if it doesn't look like a flag or filter, treat as value
            if i + 1 < len(tokens) and not tokens[i + 1].startswith(OPTION_PREFIX):
                next_tok = tokens[i + 1]
                # Only consume as value if it doesn't look like a filter expression
                if _FILTER_RE.match(next_tok) is None:
                    options[key] = next_tok
                    i += 2
                    continue
            options[key] = True
            i += 1
            continue

        # Filter: KEY OP VALUE (no spaces around op inside the token)
        m = _FILTER_RE.match(tok)
        if m:
            fkey, fop, fval = m.group(1), m.group(2), m.group(3)
            fval = fval.strip()
            if fval.startswith((">", "<", "=", "!")):
                raise CommandParseError(f"Malformed filter expression: {tok!r}")
            filters.append(CommandFilter(key=fkey, op=_validate_op(fop), value=fval))
            i += 1
            continue

        # Positional
        positional.append(tok)
        i += 1

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
