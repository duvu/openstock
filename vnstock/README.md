# vnstock — Data-Only Market Data Toolkit

`vnstock` is a Python library for extracting and normalizing financial market data, with a strong focus on Vietnamese securities data.

This fork is maintained as a **data-only market data layer**. It intentionally excludes charting, bot notification, broker login, portfolio management, order placement, and trading execution.

> Vietnamese summary: fork này tập trung vào **thu thập dữ liệu, chuẩn hóa schema, kiểm tra chất lượng dữ liệu, và so sánh/fallback giữa providers**. Không dùng cho đặt lệnh, quản lý tài khoản, hay tự động giao dịch.

---

## Current Scope

| Area | Status |
|---|---|
| Unified UI | Available through `Market`, `Reference`, `Fundamental`, `Retail` |
| Vietnam equity OHLCV | KBS default, with VCI/DNSE/TCBS alternatives for core equity market paths |
| Price board / quote | KBS default, VCI/DNSE/TCBS alternatives for core equity market paths |
| Intraday trades | KBS default, VCI/DNSE alternatives where supported (TCBS experimental) |
| Index / ETF / futures / warrant / bond market paths | Primarily KBS-backed |
| Global OHLCV | MSN/FMP where available |
| Fund data | FMarket-backed fund NAV/holding data |
| Cache layer | Memory/SQLite cache with env config |
| Data quality layer | OHLCV, price board, intraday validators |
| Provider hardening | Capability registry, schema drift detection, comparison, health scoring, contract fixtures/tests |
| Live smoke tests | Available but disabled by default and gated by env vars |
| Broker execution | Explicitly out of scope |

---

## Install

```bash
pip install -U vnstock
```

For development:

```bash
git clone https://github.com/duvu/vnstock.git
cd vnstock
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
```

Python support follows `pyproject.toml`: Python `>=3.10`.

---

## Quick Start

```python
from vnstock import Market, Reference, Fundamental

market = Market()
ref = Reference()
fa = Fundamental()

# Historical OHLCV, default source is KBS for Vietnamese equities
bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    interval="1D",
)

# Use an alternative provider where the UI registry supports it
bars_dnse = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    interval="1D",
    source="DNSE",
)

# TCBS provider — unofficial public endpoints, data-only, not the default
bars_tcbs = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    interval="1D",
    source="TCBS",
)

# Price board snapshot
quote = market.equity.quote(symbols_list=["FPT", "VCB", "TCB"])

# Company reference data
profile = ref.company.info(symbol="FPT")

# Financial statements
balance_sheet = fa.equity.balance_sheet(symbol="TCB", period="year")
```

---

## Data Quality Validation

Quality validation is available for market datasets, but it is **off by default** unless explicitly enabled.

Per-call usage:

```python
bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    validate=True,
    quality_mode="warn",  # "off" | "warn" | "strict"
)

report = bars.attrs.get("quality")
```

Global env config:

```bash
export VNSTOCK_QUALITY_ENABLED=true
export VNSTOCK_QUALITY_MODE=warn
export VNSTOCK_QUALITY_ATTACH_REPORT=true
```

Current validators:

| Dataset | Validator status |
|---|---|
| `ohlcv` | Schema, temporal, numeric, OHLC consistency, freshness checks |
| `price_board` | Required columns, duplicate symbols, price-band consistency, bid/ask checks, non-negative volumes, freshness checks |
| `intraday_trades` | Required columns, trade price/volume, duplicate id, match type, optional session-time checks |
| `reference` / `fundamental` | Planned, not yet implemented as first-class quality contracts |

See: [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md).

---

## Provider Hardening

The provider hardening layer is under `vnstock/core/provider/`.

It provides:

- provider capability declarations
- schema drift detection
- OHLCV cross-provider comparison
- provider health scoring
- provider capability matrix generation
- offline provider contract tests using fixtures
- live smoke test scaffold gated by environment variables

See: [`docs/PROVIDER_HARDENING.md`](docs/PROVIDER_HARDENING.md).

---

## Foreign Investor Data

The current system exposes foreign investor fields mainly through price board snapshots:

- `foreign_buy_volume`
- `foreign_sell_volume`
- `foreign_room`

This is enough for session/snapshot inspection, but not yet a full daily time-series foreign-flow dataset. Historical foreign flow remains a roadmap item.

---

## Cache Configuration

The cache layer supports memory and SQLite backends.

```bash
export VNSTOCK_CACHE_ENABLED=true
export VNSTOCK_CACHE_BACKEND=memory   # memory | sqlite
export VNSTOCK_CACHE_TTL=300
export VNSTOCK_CACHE_MAX_SIZE=100
export VNSTOCK_CACHE_PATH=~/.vnstock/cache.db
```

Live or near-live data such as price board snapshots and intraday trades should use conservative TTLs or disable cache per call when freshness matters.

---

## Live Smoke Tests

Live tests are disabled by default. To run them manually:

```bash
VNSTOCK_LIVE_TESTS=true PYTHONPATH=. pytest tests/live/providers -m live -v
```

Optional filters:

```bash
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=DNSE pytest tests/live/providers -m live
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=TCBS VNSTOCK_LIVE_SYMBOLS=FPT pytest tests/live/providers/test_tcbs_live.py -m live -v
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_SYMBOLS=FPT pytest tests/live/providers -m live
```

Live tests are not part of the default CI path.

---

## Development Checks

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
```

Targeted provider/quality checks:

```bash
PYTHONPATH=. pytest tests/unit/core/quality tests/unit/core/provider tests/contracts/providers -q
```

---

## Examples

Runnable scripts demonstrating every data provider:

```bash
python examples/kbs_example.py        # KBS  — default provider
python examples/vci_example.py        # VCI
python examples/dnse_example.py       # DNSE
python examples/msn_example.py        # MSN
python examples/tcbs_example.py       # TCBS
FMP_API_KEY=<key> python examples/fmp_example.py    # FMP (key required)
python examples/fmarket_example.py    # FMarket funds
```

See [`examples/README.md`](examples/README.md) for the full provider reference table.

---

## Documentation Map

| Document | Purpose |
|---|---|
| [`roadmap.md`](roadmap.md) | Current roadmap focused on data collection foundation |
| [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md) | Quality validation behavior, modes, env config, and limitations |
| [`docs/PROVIDER_HARDENING.md`](docs/PROVIDER_HARDENING.md) | Provider capabilities, drift detection, comparison, health scoring, tests |
| [`docs/REMOVED_APIS.md`](docs/REMOVED_APIS.md) | APIs removed from the data-only fork |
| [`docs/COMPATIBILITY_MATRIX.md`](docs/COMPATIBILITY_MATRIX.md) | Compatibility notes versus upstream |
| [`requirements.lock`](requirements.lock) | Locked dependency set for reproducible dev/test/build |

---

## Non-Goals

This package must not include:

- broker login or session management
- order placement, order cancel/modify, portfolio, or account APIs
- trading bots or automated execution
- investment advice, signals, or recommendations
- charting or notification integrations in the core package

Keep those concerns in application-level projects, not in the data extraction library.

---

## Disclaimer

`vnstock` is a data extraction and normalization tool. It is not an official data vendor, broker, investment adviser, or trading system. Extracted data can be incomplete, delayed, inconsistent, or wrong. Validate data before using it in research, reporting, or any financial workflow.

Do not treat library output as investment advice.

---

## License

This project uses a custom license oriented toward personal, research, and non-commercial use. See the repository license and upstream license notes before using it in commercial or organizational workflows.
