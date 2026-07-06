"""Slash-command grammar constants and token patterns."""

from __future__ import annotations

import re

# Valid command name: starts with letter, followed by letters/digits/underscores/hyphens
COMMAND_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

# Filter operators, ordered longest-first to avoid prefix ambiguity
FILTER_OPS = ["not_contains", "contains", "!=", ">=", "<=", ">", "<", "="]

# Option prefix
OPTION_PREFIX = "--"

# Quote characters for multi-word positional values
QUOTE_CHARS = ('"', "'")
