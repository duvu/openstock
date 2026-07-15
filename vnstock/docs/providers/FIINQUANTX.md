# FiinQuantX provider

FiinQuantX is an optional, licensed, data-read provider. The base `vnstock`
package does not install or vendor its SDK, credentials, session state, raw
licensed rows, or proprietary source.

## Current evidence state

The provider is an optional integration. It stays disabled unless the approved
SDK version, both credential environment variables, and
`VNSTOCK_FIINQUANTX_LICENSED=true` are present. This acknowledgement is an
operational guard; it is not a substitute for commercial approval.

The runtime-verified, experimental datasets are:

| Dataset | Method | Contract |
|---|---|---|
| `equity.ohlcv` | `Fetch_Trading_Data(realtime=False)` | bounded daily OHLCV |
| `index.ohlcv` | `Fetch_Trading_Data(realtime=False)` | bounded daily OHLCV |
| `reference.index_membership_snapshot` | `TickerList(index)` | current observation only |
| `reference.sector_membership_snapshot` | `TickerList(sector)` | current observation only |

`reference.company_info` remains disabled. The bounded `BasicInfor` probe did
not establish a stable reference contract, so the provider will return an
explicit unsupported-dataset error instead of falling back to another source.

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

## Runtime configuration

Configure these values in the deployment environment, never in source,
fixtures, request parameters, logs, or responses:

```text
FIINQUANT_USERNAME=<licensed-account>
FIINQUANT_PASSWORD=<licensed-secret>
VNSTOCK_FIINQUANTX_LICENSED=true
```

For the local service image, set `VNSTOCK_INSTALL_FIINQUANTX=true` at build
time. The Docker Compose deployment publishes only `127.0.0.1:6900`.

## Commercial and persistence decisions

| Mode | Decision before licensed approval |
|---|---|
| In-memory cache | Allowed only for the local process and approved account |
| SQLite or normalized files | Disabled until the license explicitly permits persistence |
| DuckDB/Postgres | Disabled until commercial and multi-user terms are reviewed |
| Raw archive | Prohibited by default |
| Local REST | Only a licensed, credential-isolated operator may enable it |
| Multi-user/public exposure | Prohibited by default |
| Bulk export | Prohibited by default |
| Model training and derived analytics | Require a separate written license decision |
| Synthetic fixtures | Allowed; must contain no credentials or licensed production values |

## Boundary and capabilities

The provider is limited to synchronous, allowlisted data methods. Broker,
account, cash, buying power, loan, margin, order, position, portfolio,
allocation, transfer, and execution surfaces are forbidden. Streaming,
WebSocket, order-book, and realtime quote methods are not enabled by this MVP.

The implemented first capability set is bounded historical equity/index OHLCV
and current index/sector membership snapshots. It intentionally excludes
company reference information, realtime data, streaming, order-book data and
all broker/account/trading surfaces.

Membership timestamps are local observation times. They are not effective
dates and must not be used to infer historical index or sector composition.

For OHLCV, the supported request controls are `symbol`, `count_back` (1 to
10,000), and `interval=1D`. The provider sends the verified bounded SDK
request policy (`adjusted=True`, `lasted=False`); callers cannot override
those controls until their semantics are verified. Unknown vendor columns are
dropped before the canonical response is returned.

Credentials must come from local environment or credential abstractions. They
must never be passed as dataset parameters or written to logs, diagnostics,
dataframes, service responses, or fixtures.
