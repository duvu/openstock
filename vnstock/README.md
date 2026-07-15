# vnstock — data-only market data platform

`vnstock` is the data layer of OpenStock. It extracts, normalizes, validates and serves financial market data, with a strong focus on Vietnamese securities.

```text
vnstock  = provider plugins + canonical dataset contracts + quality/routing/service
vnalpha  = research warehouse + analysis + watchlists + backtests + AI workspace
```

The package is intentionally data-only. It excludes broker/account access, portfolio mutation, order placement, allocation, margin, transfer, trading bots and execution.

## Product objective

Develop a provider-independent Vietnamese financial data platform that can:

- support public and credentialed data providers through one plugin contract;
- normalize provider-specific responses into canonical datasets;
- distinguish valid empty data, partial data, schema drift and provider failure;
- validate data quality before downstream research consumes it;
- expose provider health, routing, freshness and provenance;
- serve bounded read-only data to `vnalpha`, notebooks, batch jobs and approved tools.

Current priority and delivery order are maintained in [the root roadmap](../ROADMAP.md) and GitHub issue [#90](https://github.com/duvu/openstock/issues/90), not in component planning documents.

## Current scope

| Area | Status |
|---|---|
| Plugin platform | `ProviderPlugin`, `PluginRegistry`, auth/health-aware `PluginRouter`, synchronous `PluginRuntime` and `DataResult` are implemented |
| Local service | Canonical read-only REST endpoints, default localhost binding and forbidden broker/account routes |
| Vietnam OHLCV | KBS default; VCI, DNSE and TCBS alternatives where supported |
| Quote and intraday | Public-provider paths where supported; quality and freshness controls apply |
| Index/ETF/futures/warrant/bond data | Primarily KBS-backed |
| Global market data | MSN/FMP where available |
| Fund data | FMARKET NAV and fund data |
| FiinQuantX | Experimental, explicit-source-only licensed provider for bounded daily equity/index OHLCV and current index/sector membership snapshots |
| Cache | Memory/SQLite for permitted data; commercial-provider persistence follows provider-specific license policy |
| Quality | OHLCV, price-board and intraday validators; reference/fundamental quality contracts remain incomplete |
| Provider hardening | Capability contracts, schema drift, comparison, health, routing diagnostics, fixtures and opt-in live tests |
| Trading execution | Permanently out of scope |

The current FiinQuantX slice is deliberately limited. Commercial approval, complete entitlement/quota/session behavior, company reference and later flow/fundamental contracts remain open work under issues #105/#106. See [`docs/providers/FIINQUANTX.md`](docs/providers/FIINQUANTX.md).

## Architecture

```text
public/credentialed data source
→ built-in ProviderPlugin
→ PluginRegistry
→ auth- and health-aware PluginRouter
→ synchronous PluginRuntime.fetch()
→ provider-specific normalizer
→ canonical DatasetContract and quality validation
→ DataResult with safe diagnostics and lineage
→ Python UI or localhost read-only service
→ vnalpha ingestion and research workflows
```

Public and service data fetches must not bypass `PluginRuntime`. Streaming/WebSocket subscriptions need a separate lifecycle and are not represented as ordinary synchronous fetches.

## Installation

```bash
pip install -U vnstock
```

For development:

```bash
git clone https://github.com/duvu/openstock.git
cd openstock/vnstock
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
```

Python support follows `pyproject.toml` and is currently Python `>=3.10`.

Commercial SDKs are optional and are not vendored by `vnstock`. Follow the exact-version, credential and license instructions in the provider-specific documentation.

## Quick start

```python
from vnstock import Fundamental, Market, Reference

market = Market()
reference = Reference()
fundamental = Fundamental()

bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    interval="1D",
)

bars_vci = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    interval="1D",
    source="VCI",
)

quote = market.equity.quote(symbols_list=["FPT", "VCB", "TCB"])
profile = reference.company.info(symbol="FPT")
balance_sheet = fundamental.equity.balance_sheet(symbol="TCB", period="year")
```

For the licensed FiinQuantX experimental path, use only documented canonical endpoints and explicit `source="FIINQUANTX"` after completing local SDK, credential and license configuration. Explicit selection returns a typed failure rather than silently falling back.

## Data quality

Quality validation is available for market datasets and is opt-in unless a higher-level ingestion contract requires it.

```python
bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2024-06-30",
    validate=True,
    quality_mode="warn",  # off | warn | strict
)

quality = bars.attrs.get("quality")
```

Environment configuration:

```bash
export VNSTOCK_QUALITY_ENABLED=true
export VNSTOCK_QUALITY_MODE=warn
export VNSTOCK_QUALITY_ATTACH_REPORT=true
```

| Dataset | Validator status |
|---|---|
| OHLCV | Schema, temporal, numeric, OHLC consistency and freshness checks |
| Price board | Required columns, duplicates, price bands, bid/ask, non-negative volumes and freshness |
| Intraday trades | Required columns, trade values, duplicates, match type and optional session checks |
| Reference/fundamental | First-class quality contracts remain planned |

See [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md).

## Provider platform and diagnostics

The provider platform provides:

- capability declarations and contract validation;
- provider-specific authentication specifications;
- health- and auth-aware routing with explicit-source semantics;
- cooldown and safe routing decisions;
- schema-drift detection;
- OHLCV cross-provider comparison;
- provider health scoring and capability matrices;
- synthetic offline fixtures and opt-in live smoke tests;
- safe service metadata without credentials or session state.

See:

- [`docs/PLUGIN_ARCHITECTURE_STATUS.md`](docs/PLUGIN_ARCHITECTURE_STATUS.md)
- [`docs/PROVIDER_HARDENING.md`](docs/PROVIDER_HARDENING.md)
- [`docs/providers/FIINQUANTX.md`](docs/providers/FIINQUANTX.md)

## Credentialed data providers

Credentialed data-provider authentication is permitted when it is used only to access licensed data through the approved auth layer.

Credentials must not appear in:

- dataset parameters;
- REST query/body fields;
- DataFrame attributes or `DataResult` diagnostics;
- logs, fixtures, notebooks, MCP inputs or assistant tool parameters.

Broker login, account sessions, order sessions and trading execution remain prohibited even if a vendor SDK contains those methods.

## Cache and persistence

```bash
export VNSTOCK_CACHE_ENABLED=true
export VNSTOCK_CACHE_BACKEND=memory   # memory | sqlite
export VNSTOCK_CACHE_TTL=300
export VNSTOCK_CACHE_MAX_SIZE=100
export VNSTOCK_CACHE_PATH=~/.vnstock/cache.db
```

Near-live data should use conservative TTLs or bypass cache. Commercial-provider data may be cached or persisted only when the provider-specific license decision permits it.

## Live smoke tests

Live tests are disabled by default:

```bash
VNSTOCK_LIVE_TESTS=true PYTHONPATH=. pytest tests/live/providers -m live -v
```

Provider filters can be applied through `VNSTOCK_LIVE_PROVIDERS` and `VNSTOCK_LIVE_SYMBOLS`. Licensed providers require their additional explicit acknowledgement flags and must not print raw licensed rows or secrets.

## Development checks

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
```

Targeted provider checks:

```bash
PYTHONPATH=. pytest tests/unit/core/provider tests/contracts/providers -q
```

## Documentation map

| Document | Purpose |
|---|---|
| [`../ROADMAP.md`](../ROADMAP.md) | Canonical roadmap pointer and governance |
| [`roadmap.md`](roadmap.md) | Historical platform-evolution design; not a live delivery queue |
| [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md) | Quality behavior and limitations |
| [`docs/PROVIDER_HARDENING.md`](docs/PROVIDER_HARDENING.md) | Capabilities, drift, comparison, health, routing and tests |
| [`docs/PLUGIN_ARCHITECTURE_STATUS.md`](docs/PLUGIN_ARCHITECTURE_STATUS.md) | Accepted plugin-platform architecture and closure status |
| [`docs/REMOVED_APIS.md`](docs/REMOVED_APIS.md) | APIs removed from the data-only fork |
| [`docs/COMPATIBILITY_MATRIX.md`](docs/COMPATIBILITY_MATRIX.md) | Compatibility notes versus upstream |

## Permanent non-goals

The core package must not include:

- broker/account login or session management;
- order placement, modification or cancellation;
- portfolio mutation, allocation or rebalance execution;
- cash, buying power, loan, margin or transfer workflows;
- trading bots or automated execution;
- investment recommendations or advice;
- charting and notification delivery in the core data layer.

## Disclaimer

`vnstock` is a data extraction and normalization tool, not an official data vendor, broker, investment adviser or trading system. Provider output can be incomplete, delayed, revised or wrong. Validate data and review provider licenses before using it in research or organizational workflows.