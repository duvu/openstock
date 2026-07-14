# FiinQuantX provider

FiinQuantX is an optional, licensed, data-read provider. The base `vnstock`
package does not install or vendor its SDK, credentials, session state, raw
licensed rows, or proprietary source.

## Current evidence state

The repository contains documentation and an offline-safe provider foundation.
No licensed SDK or credentials are available in the normal development
environment, so all FiinQuantX capabilities remain disabled. Documentation is
not runtime evidence.

## Licensed installation

Install the reviewed exact version in an isolated environment using the
official package index:

```text
python -m venv .venv-fiinquantx
. .venv-fiinquantx/bin/activate
python -m pip install --upgrade pip
python -m pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx==0.1.64
python -c "import importlib.metadata; print(importlib.metadata.version('fiinquantx'))"
```

The operator must record the wheel hash or equivalent integrity decision,
Python/OS compatibility, and the approved commercial license before enabling a
capability. Do not use an unpinned mixed-index installation.

## Commercial and persistence decisions

| Mode | Decision before licensed approval |
|---|---|
| In-memory cache | Allowed only for the local process and approved account |
| SQLite or normalized files | Disabled until the license explicitly permits persistence |
| DuckDB/Postgres | Disabled until commercial and multi-user terms are reviewed |
| Raw archive | Prohibited by default |
| Local REST | Disabled until exposure terms and credential isolation are reviewed |
| Multi-user/public exposure | Prohibited by default |
| Bulk export | Prohibited by default |
| Model training and derived analytics | Require a separate written license decision |
| Synthetic fixtures | Allowed; must contain no credentials or licensed production values |

## Boundary and capabilities

The provider is limited to synchronous, allowlisted data methods. Broker,
account, cash, buying power, loan, margin, order, position, portfolio,
allocation, transfer, and execution surfaces are forbidden. Streaming,
WebSocket, order-book, and realtime quote methods are not enabled by this MVP.

The planned first capability set is historical equity/index OHLCV, company
reference information, and current index/sector membership snapshots. These
remain disabled until the licensed probes verify return shapes, units,
timestamps, entitlement and failure semantics.

Credentials must come from local environment or credential abstractions. They
must never be passed as dataset parameters or written to logs, diagnostics,
dataframes, service responses, or fixtures.
