"""
VCI Provider Example
====================
Demonstrates all public methods available through the VCI data provider.
VCI provides Vietnamese stock market data (no credentials required).

Run:
    python examples/vci_example.py
"""

from __future__ import annotations

from vnstock.explorer.vci.company import Company
from vnstock.explorer.vci.financial import Finance
from vnstock.explorer.vci.listing import Listing
from vnstock.explorer.vci.quote import Quote
from vnstock.explorer.vci.trading import Trading

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
        # VCI intraday may be unavailable outside trading hours
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

    # ------------------------------------------------------------------ #
    # Listing — All listed symbols
    # ------------------------------------------------------------------ #
    section("Listing.all_symbols() — Full symbol list")
    try:
        lst = Listing()
        df = lst.all_symbols()
        print(df.head())
        print(f"Total symbols: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Listing — Symbols by industry
    # ------------------------------------------------------------------ #
    section("Listing.symbols_by_industries() — Symbols grouped by industry")
    try:
        lst = Listing()
        df = lst.symbols_by_industries()
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Company — Overview
    # ------------------------------------------------------------------ #
    section("Company.overview() — Company profile")
    try:
        co = Company(symbol=SYMBOL)
        df = co.overview()
        print(df.to_string(index=False))
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Company — Shareholders
    # ------------------------------------------------------------------ #
    section("Company.shareholders() — Major shareholders")
    try:
        co = Company(symbol=SYMBOL)
        df = co.shareholders()
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Finance — Balance sheet
    # ------------------------------------------------------------------ #
    section("Finance.balance_sheet() — Quarterly balance sheet")
    try:
        fin = Finance(symbol=SYMBOL, period="quarter")
        df = fin.balance_sheet()
        print(df.head(3))
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Finance — Income statement
    # ------------------------------------------------------------------ #
    section("Finance.income_statement() — Quarterly income statement")
    try:
        fin = Finance(symbol=SYMBOL, period="quarter")
        df = fin.income_statement()
        print(df.head(3))
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Finance — Cash flow
    # ------------------------------------------------------------------ #
    section("Finance.cash_flow() — Quarterly cash flow")
    try:
        fin = Finance(symbol=SYMBOL, period="quarter")
        df = fin.cash_flow()
        print(df.head(3))
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Finance — Financial ratios
    # ------------------------------------------------------------------ #
    section("Finance.ratio() — Key financial ratios")
    try:
        fin = Finance(symbol=SYMBOL, period="quarter")
        df = fin.ratio()
        print(df.head(3))
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
