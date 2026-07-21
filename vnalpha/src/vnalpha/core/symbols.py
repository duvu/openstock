"""Shared symbol canonicalization and validation (issue #315).

A single source of truth for turning the many JSON-valid-but-wrongly-typed
symbol shapes a classifier can emit into one canonical representation before the
planner and provisioning boundary ever see them.

Two failure categories are kept strictly separate:

* ``INVALID_SYMBOL_FORMAT`` — the value is not a well-formed ticker (brackets,
  quotes, commas, serialized collections, objects, …). Raised by
  :func:`validate_ticker` / :func:`canonicalize_symbol_entities` as
  :class:`SymbolFormatError`. This is a *syntax* failure decided without any
  warehouse access.
* ``SYMBOL_NOT_FOUND`` — the value is a well-formed ticker but is not present in
  ``symbol_master``. This is a *membership* failure decided by the data layer,
  never here.

The canonical contract for a symbol-requiring request is::

    symbols: tuple[str, ...]
    primary_symbol: str | None

which the compatibility dictionary mirrors as ``{"symbol": "FPT",
"symbols": ["FPT"]}`` for a single-symbol request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Stable failure-category identifiers. Syntax validation (INVALID_SYMBOL_FORMAT)
# is deliberately distinct from membership validation (SYMBOL_NOT_FOUND).
INVALID_SYMBOL_FORMAT = "INVALID_SYMBOL_FORMAT"
SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"

# Minimum shared ticker grammar: an uppercase letter followed by 1–11 uppercase
# letters/digits. Rejects brackets, quotes, commas, whitespace and serialized
# collection syntax by construction.
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")

# Leading marker tokens the Vietnamese classifier sometimes keeps in the symbol
# list ("co phieu" → "CP", "chung khoan" → "CK"). They are never the ticker
# themselves, so a marker followed by a real ticker collapses to the ticker.
_MARKER_PREFIXES = frozenset({"CP", "CK"})


class SymbolFormatError(ValueError):
    """A symbol value is not a well-formed ticker (INVALID_SYMBOL_FORMAT).

    Carries the stable ``category`` so callers can present the typed syntax
    failure and keep it distinct from a membership (SYMBOL_NOT_FOUND) failure.
    """

    category = INVALID_SYMBOL_FORMAT

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CanonicalSymbols:
    """The single canonical representation of a request's symbols."""

    symbols: tuple[str, ...]
    primary_symbol: str | None

    def as_entities(self) -> dict[str, Any]:
        """Return the normalized compatibility mapping.

        A single-symbol request yields ``{"symbol": "FPT", "symbols": ["FPT"]}``;
        an empty request yields ``{"symbol": None, "symbols": []}``.
        """
        return {
            "symbol": self.primary_symbol,
            "symbols": list(self.symbols),
        }


def is_valid_ticker(value: object) -> bool:
    """Return True when *value* is already a well-formed uppercase ticker."""
    return isinstance(value, str) and TICKER_PATTERN.fullmatch(value) is not None


def validate_ticker(value: object) -> str:
    """Uppercase/trim *value* and confirm it is a well-formed ticker.

    Raises :class:`SymbolFormatError` (INVALID_SYMBOL_FORMAT) for anything that
    is not a single well-formed ticker string, including serialized list/quote
    syntax that would otherwise reach the warehouse as a literal.
    """
    if not isinstance(value, str):
        raise SymbolFormatError(
            f"{INVALID_SYMBOL_FORMAT}: expected a ticker string, "
            f"got {type(value).__name__}."
        )
    candidate = value.strip().upper()
    if not candidate:
        raise SymbolFormatError(f"{INVALID_SYMBOL_FORMAT}: empty ticker.")
    if TICKER_PATTERN.fullmatch(candidate) is None:
        raise SymbolFormatError(
            f"{INVALID_SYMBOL_FORMAT}: {value!r} is not a valid ticker "
            f"(expected {TICKER_PATTERN.pattern})."
        )
    return candidate


def _looks_like_serialized_collection(text: str) -> bool:
    return len(text) >= 2 and text[0] in "[(" and text[-1] in ")]"


def _split_serialized_collection(text: str) -> list[str]:
    inner = text[1:-1]
    return [part.strip().strip("'\"").strip() for part in inner.split(",")]


def _coerce_tokens(value: object) -> list[str]:
    """Coerce one raw symbol value into candidate token strings.

    Understands the JSON-valid-but-mistyped shapes a classifier emits — a list,
    a serialized list literal (``"['FPT']"``), or a comma-joined string — while
    refusing to stringify an arbitrary object into a ticker literal.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_coerce_tokens(item))
        return tokens
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if _looks_like_serialized_collection(text):
            return [part for part in _split_serialized_collection(text) if part]
        if "," in text:
            return [
                part.strip().strip("'\"") for part in text.split(",") if part.strip()
            ]
        return [text.strip("'\"")]
    # Numbers, dicts and any other object cannot be a ticker; never str() them
    # into a literal (rule #4).
    raise SymbolFormatError(
        f"{INVALID_SYMBOL_FORMAT}: cannot derive a ticker from "
        f"{type(value).__name__} value."
    )


def _strip_marker_prefix(tokens: list[str]) -> list[str]:
    if len(tokens) >= 2 and tokens[0] in _MARKER_PREFIXES:
        return tokens[1:]
    return tokens


def _dedupe_validated(tokens: list[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for token in tokens:
        ticker = validate_ticker(token)
        if ticker not in seen:
            seen.append(ticker)
    return tuple(seen)


def canonicalize_symbol_entities(entities: dict[str, Any]) -> CanonicalSymbols:
    """Normalize the ``symbol``/``symbols`` entities into one representation.

    Accepted shapes (``"FPT"``, ``["FPT"]``, ``"['FPT']"``, ``'["FPT"]'`` …)
    resolve to a single canonical ticker. Malformed shapes — an object value, a
    ``symbol`` scalar carrying multiple tickers, or a ``symbol``/``symbols``
    contradiction — raise :class:`SymbolFormatError` so they are rejected before
    the planner rather than normalized into a wrong literal.
    """
    symbol_tokens = _coerce_tokens(entities.get("symbol"))
    symbols_tokens = _coerce_tokens(entities.get("symbols"))

    # The ``symbol`` field is a single-symbol field. If it expands to more than
    # one ticker (e.g. "FPT,VCB" or "[FPT, VCB]") it is malformed; genuine
    # multi-symbol requests must arrive through ``symbols``.
    symbol_field = _strip_marker_prefix(symbol_tokens)
    if len(symbol_field) > 1:
        raise SymbolFormatError(
            f"{INVALID_SYMBOL_FORMAT}: 'symbol' must be a single ticker, "
            f"got {entities.get('symbol')!r}."
        )
    primary_from_symbol = validate_ticker(symbol_field[0]) if symbol_field else None

    canonical_symbols = _dedupe_validated(_strip_marker_prefix(symbols_tokens))

    if primary_from_symbol is not None:
        if canonical_symbols and primary_from_symbol not in canonical_symbols:
            raise SymbolFormatError(
                f"{INVALID_SYMBOL_FORMAT}: 'symbol' {primary_from_symbol!r} "
                f"contradicts 'symbols' {list(canonical_symbols)!r}."
            )
        if not canonical_symbols:
            canonical_symbols = (primary_from_symbol,)
        primary = primary_from_symbol
    else:
        primary = canonical_symbols[0] if canonical_symbols else None

    return CanonicalSymbols(symbols=canonical_symbols, primary_symbol=primary)


def apply_canonical_symbols(entities: dict[str, Any]) -> CanonicalSymbols:
    """Canonicalize *entities* in place and return the canonical symbols.

    When at least one symbol resolves, ``entities['symbol']`` and
    ``entities['symbols']`` are rewritten to the canonical mapping. When none
    resolve the keys are left untouched so downstream recovery / missing-symbol
    handling can run. Raises :class:`SymbolFormatError` for malformed input.
    """
    canonical = canonicalize_symbol_entities(entities)
    if canonical.primary_symbol is not None:
        entities["symbol"] = canonical.primary_symbol
        entities["symbols"] = list(canonical.symbols)
    return canonical


__all__ = [
    "INVALID_SYMBOL_FORMAT",
    "SYMBOL_NOT_FOUND",
    "TICKER_PATTERN",
    "SymbolFormatError",
    "CanonicalSymbols",
    "is_valid_ticker",
    "validate_ticker",
    "canonicalize_symbol_entities",
    "apply_canonical_symbols",
]
