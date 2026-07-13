from __future__ import annotations

import re


class SymbolPathError(ValueError):
    pass


_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{0,15}$")
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"})


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if (
        not symbol
        or symbol in _RESERVED
        or not _SYMBOL_RE.fullmatch(symbol)
        or "/" in value
        or "\\" in value
        or ":" in value
    ):
        raise SymbolPathError("Symbol must be a safe canonical identifier.")
    return symbol


__all__ = ["SymbolPathError", "normalize_symbol"]
