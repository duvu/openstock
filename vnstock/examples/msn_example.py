"""
MSN Provider Example
====================
Demonstrates all public methods available through the MSN data provider.
MSN provides global financial data via Microsoft's MSN Money service
(no credentials required).

Note: MSN uses an internal `symbol_id` (not the exchange ticker).
      You must first look up the symbol_id via Listing.search_symbol()
      before calling Quote.history().

Run:
    python examples/msn_example.py
"""

from __future__ import annotations

from vnstock.explorer.msn.listing import Listing
from vnstock.explorer.msn.quote import Quote

QUERY = "FPT"  # Search term (ticker or company name)
START = "2024-01-01"
END = "2024-06-30"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    # ------------------------------------------------------------------ #
    # Listing — Search for a symbol to retrieve its MSN symbol_id
    # ------------------------------------------------------------------ #
    section("Listing.search_symbol() — Find symbol_id for a ticker")
    symbol_id = None
    try:
        lst = Listing()
        df = lst.search_symbol(query=QUERY)
        print(df.head())
        if not df.empty:
            # The first result is typically the best match
            symbol_id = df.iloc[0]["symbol_id"] if "symbol_id" in df.columns else None
            print(f"\nResolved symbol_id for '{QUERY}': {symbol_id}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Listing — Detailed info for a symbol
    # ------------------------------------------------------------------ #
    section("Listing.info() — Detailed symbol metadata")
    try:
        lst = Listing()
        df = lst.info(query=QUERY)
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Quote — OHLCV history (requires symbol_id)
    # ------------------------------------------------------------------ #
    section("Quote.history() — Daily OHLCV (using symbol_id)")
    if symbol_id is None:
        print("[SKIP] No symbol_id resolved from search — cannot fetch history.")
        return
    try:
        q = Quote(symbol_id=symbol_id)
        df = q.history(start=START, end=END, interval="1D")
        print(df.head())
        print(f"Rows: {len(df)}, Cols: {list(df.columns)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
