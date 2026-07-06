"""
DNSE Provider Example
=====================
Demonstrates all public methods available through the DNSE data provider.
DNSE provides Vietnamese stock market data (no credentials required).

Run:
    python examples/dnse_example.py
"""

from __future__ import annotations

from vnstock.explorer.dnse.quote import Quote
from vnstock.explorer.dnse.trading import Trading

SYMBOL = "FPT"
SYMBOLS = ["FPT", "VCB", "TCB"]
START = "2024-01-01"
END = "2024-06-30"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    # ------------------------------------------------------------------ #
    # Quote — OHLCV history
    # ------------------------------------------------------------------ #
    section("Quote.history() — Daily OHLCV")
    try:
        q = Quote(SYMBOL)
        df = q.history(start=START, end=END, interval="1D")
        print(df.head())
        print(f"Rows: {len(df)}, Cols: {list(df.columns)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Quote — Intraday trades
    # ------------------------------------------------------------------ #
    section("Quote.intraday() — Intraday trades")
    try:
        q = Quote(SYMBOL)
        df = q.intraday()
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Trading — Price board (batch)
    # ------------------------------------------------------------------ #
    section("Trading.price_board() — Live quotes for multiple symbols")
    try:
        t = Trading()
        df = t.price_board(symbols_list=SYMBOLS)
        print(df.head())
        print(f"Symbols returned: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
