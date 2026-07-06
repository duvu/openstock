"""
FMarket Provider Example
========================
Demonstrates all public methods available through the FMarket fund data provider.
FMarket provides mutual fund data from the Vietnamese market (no credentials required).

Run:
    python examples/fmarket_example.py
"""

from __future__ import annotations

from vnstock.explorer.fmarket.fund import Fund

# A well-known Vietnamese equity fund used in the demos below
FUND_SYMBOL = "SSISCA"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    fund = Fund()

    # ------------------------------------------------------------------ #
    # Listing — All available funds
    # ------------------------------------------------------------------ #
    section("Fund.listing() — All funds on FMarket")
    try:
        df = fund.listing()
        print(df.head())
        print(f"Total funds: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Filter — Search for a specific fund by symbol
    # ------------------------------------------------------------------ #
    section(f"Fund.filter() — Filter/search for '{FUND_SYMBOL}'")
    try:
        df = fund.filter(symbol=FUND_SYMBOL)
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # NAV report — Historical net asset value
    # ------------------------------------------------------------------ #
    section(f"Fund.nav_report() — NAV history for '{FUND_SYMBOL}'")
    try:
        df = fund.nav_report(symbol=FUND_SYMBOL)
        print(df.head())
        print(f"NAV records: {len(df)}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Top holdings — Largest stock positions
    # ------------------------------------------------------------------ #
    section(f"Fund.top_holding() — Top stock holdings of '{FUND_SYMBOL}'")
    try:
        df = fund.top_holding(symbol=FUND_SYMBOL)
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Industry holding — Allocation by sector
    # ------------------------------------------------------------------ #
    section(f"Fund.industry_holding() — Sector allocation of '{FUND_SYMBOL}'")
    try:
        df = fund.industry_holding(symbol=FUND_SYMBOL)
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------ #
    # Asset holding — Allocation by asset class
    # ------------------------------------------------------------------ #
    section(f"Fund.asset_holding() — Asset class allocation of '{FUND_SYMBOL}'")
    try:
        df = fund.asset_holding(symbol=FUND_SYMBOL)
        print(df.head())
    except Exception as exc:
        print(f"[ERROR] {exc}")


if __name__ == "__main__":
    main()
