"""Service dataset mapper.

Maps canonical HTTP paths to dataset names and extracts query params
for :class:`~vnstock.core.runtime.plugin_runtime.PluginRuntime`.

Usage::

    from vnstock.service.dataset_mapper import path_to_dataset, MapperError

    dataset = path_to_dataset("/v1/equity/ohlcv")
    # "equity.ohlcv"

    dataset = path_to_dataset("/v1/market/ohlcv")  # deprecated alias
    # "equity.ohlcv"  (with DeprecationWarning)
"""

from __future__ import annotations

import warnings

# ---------------------------------------------------------------------------
# Canonical path → dataset name mapping
# ---------------------------------------------------------------------------

_CANONICAL: dict[str, str] = {
    "/v1/equity/ohlcv": "equity.ohlcv",
    "/v1/equity/quote": "equity.quote",
    "/v1/equity/intraday-trades": "equity.intraday_trades",
    "/v1/index/ohlcv": "index.ohlcv",
    "/v1/reference/symbols": "reference.symbols",
    "/v1/company/info": "reference.company_info",
    "/v1/fundamental/balance-sheet": "fundamental.balance_sheet",
    "/v1/fundamental/income-statement": "fundamental.income_statement",
    "/v1/fundamental/cash-flow": "fundamental.cash_flow",
    "/v1/fundamental/financial-ratio": "fundamental.financial_ratio",
    "/v1/fund/nav": "fund.nav",
    "/v1/fund/holdings": "fund.holdings",
}

# Deprecated aliases → canonical dataset name
_ALIASES: dict[str, str] = {
    "/v1/market/ohlcv": "equity.ohlcv",
    "/v1/reference/listing": "reference.symbols",
}

# Query params forwarded to the runtime
_RUNTIME_PARAMS = frozenset({"source", "validate", "quality_mode"})


class MapperError(ValueError):
    """Raised when a path cannot be mapped to a dataset."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Unsupported dataset path: '{path}'")


def path_to_dataset(path: str) -> str:
    """Return the canonical dataset name for an HTTP path.

    Args:
        path: URL path string, e.g. ``"/v1/equity/ohlcv"``.

    Returns:
        Dotted dataset name, e.g. ``"equity.ohlcv"``.

    Raises:
        MapperError: If the path is not recognised.
    """
    normalised = path.rstrip("/").lower()
    if normalised in _CANONICAL:
        return _CANONICAL[normalised]
    if normalised in _ALIASES:
        warnings.warn(
            f"The endpoint '{path}' is deprecated; use the canonical equivalent.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _ALIASES[normalised]
    raise MapperError(path)


def extract_runtime_params(query: dict[str, list[str]]) -> dict[str, str]:
    """Extract runtime control params from parsed query string.

    Args:
        query: Parsed query-string dict (as returned by
            :func:`urllib.parse.parse_qs`).

    Returns:
        Dict with only ``source``, ``validate``, ``quality_mode`` keys
        (where present).
    """
    result: dict[str, str] = {}
    for key in _RUNTIME_PARAMS:
        if key in query:
            result[key] = query[key][0]
    return result
