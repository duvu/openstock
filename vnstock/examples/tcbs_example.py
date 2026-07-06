"""
TCBS Provider Example
=====================
Demonstrates all public methods available through the TCBS data provider.
TCBS provides Vietnamese stock market data via unofficial public endpoints
(no credentials required).

IMPORTANT: TCBS endpoints are unofficial and may change without notice.
           Intraday and screener features are EXPERIMENTAL.

Run:
    python examples/tcbs_example.py
"""

from __future__ import annotations

from vnstock.explorer.tcbs.company import Company
from vnstock.explorer.tcbs.financial import Finance
from vnstock.explorer.tcbs.listing import Listing
from vnstock.explorer.tcbs.quote import Quote
from vnstock.explorer.tcbs.screener import Screener
from vnstock.explorer.tcbs.trading import Trading

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
    # Quote — OHLCV history (3-endpoint fallback)
    # TCBS tries /stock/v2 → /stock-insight/v2 → /stock-insight/v1
    # ------------------------------------------------------------------ #
    section("Quote.history() — Daily OHLCV (3-endpoint fallback)")
    try:
        q = Quote(SYMBOL)
        df = q.history(start=START, end=END, interval="1D")
        print(df.head())
        # df.attrs carries metadata including which endpoint was used
        endpoint_used = df.attrs.get("endpoint_variant", "unknown")
        print(f"Rows: {len(df)} | Endpoint used: {endpoint_used}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Quote — Intraday trades (EXPERIMENTAL)
    # ------------------------------------------------------------------ #
    section("Quote.intraday() — Intraday trades [EXPERIMENTAL]")
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
    # Listing — Industry classification for a single symbol
    # ------------------------------------------------------------------ #
    section("Listing.symbol_industry() — Industry classification")
    try:
        lst = Listing()
        df = lst.symbol_industry(symbol=SYMBOL)
        print(df.to_string(index=False))
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
    # Company — Major shareholders
    # ------------------------------------------------------------------ #
    section("Company.shareholders() — Major shareholders")
    try:
        co = Company(symbol=SYMBOL)
        df = co.shareholders()
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Company — Dividend history
    # ------------------------------------------------------------------ #
    section("Company.dividends() — Dividend history")
    try:
        co = Company(symbol=SYMBOL)
        df = co.dividends()
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

    # ------------------------------------------------------------------ #
    # Screener — Scan for stocks matching criteria (EXPERIMENTAL)
    # Pass an empty filter list to return all stocks.
    # ------------------------------------------------------------------ #
    section("Screener.scan() — Stock screener [EXPERIMENTAL]")
    try:
        sc = Screener()
        df = sc.scan(filters=[], size=20)
        print(df.head())
        print(f"Results: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
