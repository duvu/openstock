# OpenStock

**OpenStock is an evidence-first, provider-independent research platform for Vietnamese equities.**

It combines a normalized market-data layer with a reproducible research workspace:

```text
vnstock  = provider plugins + canonical data contracts + quality + read-only service
vnalpha  = DuckDB research warehouse + analysis + watchlists + CLI/TUI + optional AI
```

OpenStock is built for research, education and market analysis. It is **not** a broker, portfolio manager, investment adviser or trading-execution system.

> **Project status:** active development. Stable architecture and operating procedures are documented in the repository. Current priority, dependency and delivery status are maintained in [GitHub issue #209](https://github.com/duvu/openstock/issues/209).

## Why OpenStock

Vietnamese market research often depends on provider-specific APIs, inconsistent schemas and historical data that can be revised or incomplete. OpenStock addresses those problems through explicit contracts:

- **Provider independence** — data access is routed through typed provider plugins rather than embedded source-specific calls.
- **Canonical datasets** — provider responses are normalized before downstream use.
- **Evidence before narrative** — validated warehouse data and deterministic tools outrank summaries or model prose.
- **Fail-closed behavior** — missing, stale, malformed or unsupported inputs are surfaced explicitly.
- **Reproducible research** — dates, providers, versions, assumptions, lineage and caveats remain inspectable.
- **Point-in-time direction** — historical workflows are designed to avoid survivorship and look-ahead leakage.
- **Optional AI** — deterministic research remains usable when the LLM assistant is disabled.

## Repository structure

| Path | Purpose |
|---|---|
| [`vnstock/`](vnstock/) | Data-only Python package and localhost service for market, reference and fundamental data |
| [`vnalpha/`](vnalpha/) | Terminal-first research workspace, DuckDB warehouse, analysis workflows and optional AI assistance |
| [`packaging/`](packaging/) | Debian packaging, systemd units, deployment scripts and operational verification |
| [`openspec/`](openspec/) | Requirements, design decisions, implementation tasks and validation evidence |
| [`scripts/`](scripts/) | Repository consistency and governance checks |
| [`docker-compose.yml`](docker-compose.yml) | Canonical single-host data-service and worker deployment |
| [`ROADMAP.md`](ROADMAP.md) | Stable roadmap policy and pointer to the live GitHub issue queue |

## Architecture

```text
public or credentialed data providers
                │
                ▼
       vnstock ProviderPlugin
                │
                ▼
 registry → routing → synchronous PluginRuntime
                │
                ▼
 provider normalizer → canonical DatasetContract
                │
                ▼
 quality, freshness, provenance and safe diagnostics
                │
                ▼
 localhost read-only vnstock service (:6900)
                │
                ▼
 vnalpha ingestion, validation and DuckDB warehouse
                │
                ▼
 features, scores, market/sector context and outcomes
                │
                ▼
 deterministic application services and research artifacts
                │
                ▼
       Typer CLI ─ Textual TUI ─ optional AI synthesis
```

Provider access must not bypass the `vnstock` runtime and canonical contracts. CLI, TUI, assistant and read-only API surfaces should delegate to the same typed application services.

## Current capabilities

### `vnstock` data layer

- built-in provider plugin platform with registry, routing, authentication specifications and health diagnostics;
- canonical market, reference and fundamental dataset contracts;
- Vietnamese OHLCV with KBS as the default and alternative providers where supported;
- quote, intraday, index, ETF, derivatives, bond, fund and selected global-market datasets;
- OHLCV, price-board and intraday quality validation;
- schema-drift detection, cross-provider comparison and opt-in live smoke tests;
- canonical read-only REST service bound to `127.0.0.1:6900` by default;
- optional FiinQuantX integration that remains explicit-source-only and license-gated.

See [`vnstock/README.md`](vnstock/README.md) for provider details, Python examples and current limitations.

### `vnalpha` research layer

- canonical DuckDB warehouse and explicit data-readiness evidence;
- symbol, OHLCV and index ingestion workflows;
- feature snapshots, candidate scoring and evidence-backed watchlists;
- market-regime and sector-strength snapshots;
- forward outcomes and event-study evidence;
- research artifacts, journals, source references and bounded symbol memory;
- Typer CLI and Textual TUI;
- optional LiteLLM-compatible AI gateway with explicit model routing and capability-aware fallbacks;
- audit logs, evaluation fixtures and fail-closed safety boundaries.

The point-in-time Backtest Lab and other roadmap capabilities must not be treated as implemented until their GitHub issues are closed with validation evidence.

See [`vnalpha/README.md`](vnalpha/README.md) and [`vnalpha/docs/README.md`](vnalpha/docs/README.md).

## Quick start

### One-command MVP1 startup

On a configured single Linux host, one command validates paths, starts and
health-checks `vnstock-service`, migrates the warehouse, runs the MVP1
preflight and launches the chat TUI:

```bash
packaging/scripts/openstock-mvp1-start          # start everything and open the TUI
packaging/scripts/openstock-mvp1-start --no-launch   # prepare, then print the launch command
packaging/scripts/openstock-verify --mvp1        # read-only preflight only (safe to re-run)
```

Startup is idempotent and never overwrites existing valid data or credentials.
The manual steps below remain available for development and first-time setup.

### Prerequisites

- Linux or another environment capable of running Python and Docker Compose;
- Python **3.10+**;
- Docker Engine with the Compose plugin;
- Git.

### 1. Clone and configure

```bash
git clone https://github.com/duvu/openstock.git
cd openstock
cp .env.example .env
```

The canonical single-host paths are `/var/lib/openstock/warehouse` and `/var/lib/openstock/vnstock-config`. For a local Linux installation:

```bash
sudo install -d -m 0775 -o "$USER" -g "$USER" \
  /var/lib/openstock/warehouse \
  /var/lib/openstock/vnstock-config
```

Review `.env` before enabling credentialed providers or AI. Secrets must never be committed.

### 2. Install the Python packages for development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./vnstock[dev]" -e "./vnalpha[dev]"
```

Load the host-side configuration when running `vnalpha` outside Docker:

```bash
set -a
source .env
set +a
```

### 3. Start the canonical data service

```bash
make up-vnstock
curl http://127.0.0.1:6900/healthz
```

Credentialed-provider status is handled separately:

```bash
make login-vnstock
```

### 4. Build a local research dataset

```bash
make sync
make features
make score
```

The default `make sync` workflow loads symbols, VN30 OHLCV and the VNINDEX benchmark, then builds the canonical dataset.

### 5. Launch the research workspace

```bash
make tui
```

The AI assistant is optional. Deterministic data, build, scoring and research commands continue to work when `VNALPHA_LLM_ENDPOINT`, model IDs or `VNALPHA_LLM_API_KEY` are blank.

## Container worker workflow

The root Compose file can also run bounded one-shot `vnalpha` jobs:

```bash
docker compose --profile job run --rm vnalpha-worker init
docker compose --profile job run --rm vnalpha-worker sync symbols
docker compose --profile job run --rm vnalpha-worker build canonical
```

The host-installed TUI and container worker must point to the same DuckDB file. Keep `OPENSTOCK_WAREHOUSE_DIR` and `VNALPHA_WAREHOUSE_PATH` aligned.

## Using `vnstock` as a Python library

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

profile = reference.company.info(symbol="FPT")
balance_sheet = fundamental.equity.balance_sheet(symbol="TCB", period="year")
```

Provider output can be incomplete, delayed, revised or wrong. Use validation, inspect lineage and verify provider licensing before relying on the data.

## Configuration

Start from [`.env.example`](.env.example). Important groups include:

| Configuration | Purpose |
|---|---|
| `OPENSTOCK_WAREHOUSE_DIR` | Host directory mounted as the shared DuckDB warehouse |
| `VNSTOCK_CONFIG_DIR` | Local provider configuration and credential state |
| `VNSTOCK_SERVICE_URL` | Read-only data-service endpoint used by `vnalpha` |
| `VNALPHA_WAREHOUSE_PATH` | DuckDB file used by host-side research commands |
| `VNALPHA_UNIVERSE` | Default research universe |
| `VNALPHA_LLM_*` | Optional LLM gateway configuration |
| `VNALPHA_MODEL_*` | Explicit model profiles, fallbacks and capabilities |
| `VNSTOCK_FIINQUANTX_*` | Optional licensed-runtime controls; disabled by default |

Model capabilities are explicit and fail closed. OpenStock does not infer strict JSON Schema support from a provider or model name.

## Development and validation

Repository-level checks:

```bash
make verify-repo-consistency
make validate-compose
make repo-hygiene
```

`vnalpha` checks:

```bash
make lint-vnalpha
make verify-r0
make test-vnalpha
```

`vnstock` checks:

```bash
cd vnstock
ruff check .
ruff format --check .
pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
```

A pull request is not considered ready when code, configuration, current documentation, OpenSpec or validation evidence disagree. The required `openstock-ci` merge gate runs repository consistency, both package suites and both package builds.

## Documentation map

| Document | Purpose |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) | Roadmap policy and link to the live execution queue |
| [`vnstock/README.md`](vnstock/README.md) | Data platform overview and usage |
| [`vnstock/docs/DATASET_CONTRACTS.md`](vnstock/docs/DATASET_CONTRACTS.md) | Canonical dataset contracts |
| [`vnstock/docs/DATA_QUALITY.md`](vnstock/docs/DATA_QUALITY.md) | Data-quality behavior and limitations |
| [`vnalpha/README.md`](vnalpha/README.md) | Research-layer overview |
| [`vnalpha/docs/02-system-architecture.md`](vnalpha/docs/02-system-architecture.md) | Current system architecture |
| [`vnalpha/docs/03-data-pipeline.md`](vnalpha/docs/03-data-pipeline.md) | Warehouse and data-flow contracts |
| [`vnalpha/docs/05-backtest-and-outcome.md`](vnalpha/docs/05-backtest-and-outcome.md) | Implemented outcome evidence and planned backtesting boundary |
| [`vnalpha/docs/06-ai-layer.md`](vnalpha/docs/06-ai-layer.md) | AI routing, grounding and safety |
| [`vnalpha/docs/11-deployment-architecture.md`](vnalpha/docs/11-deployment-architecture.md) | Deployment topology and operations |
| [`openspec/active-changes.yaml`](openspec/active-changes.yaml) | Non-archived specification lifecycle and evidence |

## Roadmap and contribution workflow

The live roadmap is [GitHub issue #209](https://github.com/duvu/openstock/issues/209). GitHub Issues are the source of truth for current priority, dependencies, acceptance criteria, ownership and closure evidence.

Expected delivery workflow:

1. create or select one focused primary issue;
2. state dependencies, scope, non-goals and testable acceptance criteria;
3. add OpenSpec requirements and design evidence when the change warrants it;
4. implement code, tests, configuration and current documentation in the same pull request;
5. run required CI on the exact final SHA;
6. merge, reconcile the roadmap and archive completed OpenSpec work.

A focused pull request should normally close one primary issue with `Closes #N`.

## Permanent safety boundary

OpenStock permanently excludes:

- broker or account login for trading purposes;
- order placement, modification or cancellation;
- portfolio mutation, allocation or automated rebalancing;
- cash, buying-power, loan, margin or transfer workflows;
- trading bots and automated execution;
- unrestricted shell or SQL execution through the AI assistant;
- claims of guaranteed returns or investment advice.

Credentialed access is permitted only for approved, read-only data acquisition through the documented provider boundary.

## Licensing and data rights

OpenStock does not grant rights to third-party provider data. Provider licenses, redistribution restrictions and commercial-use terms must be reviewed independently.

The `vnstock` package currently declares custom personal, research and non-commercial terms in its package metadata. This repository does not currently publish a separate root-level license file, so unrestricted reuse must not be assumed.

## Disclaimer

OpenStock is research software. It does not guarantee data accuracy, market performance or investment outcomes. Validate datasets, review provider terms and apply independent judgment before using outputs in any decision-making process.
