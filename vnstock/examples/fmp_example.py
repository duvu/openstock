"""
FMP Provider Example
====================
Demonstrates all public methods available through the FMP (Financial Modeling Prep)
data provider.

SETUP REQUIRED: FMP requires a free API key.
  1. Register at https://financialmodelingprep.com/developer/docs/
  2. Set the env var:  export FMP_API_KEY=your_key_here

Run:
    FMP_API_KEY=your_key python examples/fmp_example.py
"""

from __future__ import annotations

import os
import sys

# Check for API key before importing the provider
FMP_API_KEY = os.environ.get("FMP_API_KEY")
if not FMP_API_KEY:
    print(
        "\n[SETUP REQUIRED]\n"
        "FMP provider requires a free API key.\n"
        "  1. Register at https://financialmodelingprep.com/developer/docs/\n"
        "  2. Run:  export FMP_API_KEY=your_key_here\n"
        "  3. Retry: python examples/fmp_example.py\n"
    )
    sys.exit(0)

from vnstock.connector.fmp.quote import Quote  # noqa: E402

SYMBOL = "FPT"
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
        q = Quote(symbol=SYMBOL, api_key=FMP_API_KEY)
        df = q.history(start=START, end=END, interval="d")
        print(df.head())
        print(f"Rows: {len(df)}, Cols: {list(df.columns)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Quote — Intraday data
    # ------------------------------------------------------------------ #
    section("Quote.intraday() — Intraday OHLCV (1-minute bars)")
    try:
        q = Quote(symbol=SYMBOL, api_key=FMP_API_KEY)
        df = q.intraday(interval="m", start=START, end=END)
        print(df.head())
        print(f"Rows: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Quote — Full (real-time snapshot)
    # ------------------------------------------------------------------ #
    section("Quote.full() — Full real-time quote snapshot")
    try:
        q = Quote(symbol=SYMBOL, api_key=FMP_API_KEY)
        df = q.full()
        print(df.to_string(index=False))
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
