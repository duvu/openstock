# FiinQuantX provider

FiinQuantX is an optional, licensed, data-read provider. The base `vnstock`
package does not install or vendor its SDK, credentials, session state, raw
licensed rows, or proprietary source.

## Current evidence state

The provider is an optional integration. Its runtime requires the exact
supported SDK version and both local credential environment variables. It has
no runtime approval flag, approval reference, or expiry gate.

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

## Capability inventory and licensed probes

[`fiinquantx-capability-inventory.json`](fiinquantx-capability-inventory.json)
is the authoritative method-to-dataset inventory. It records every positive-list
SDK surface, lifecycle state, named consumer, request boundary, and the unknown
unit, timing, revision, entitlement, and evidence fields that keep a candidate
disabled.

[The 2026-07-22 licensed probe summary](fiinquantx-licensed-probe-2026-07-22.md)
records the safe runtime evidence for the exact supported SDK. It certifies the
four existing datasets through their canonical plugin paths and records why all
other candidates remain deferred.

Run the opt-in probe only in a licensed local environment and write its sanitized
report outside the checkout:

```bash
PYTHONPATH=vnstock uv run scripts/probe-fiinquantx.py \
  --output /secure/operator-evidence/fiinquantx-probe.json \
  --account-scope LICENSED_LOCAL_ACCOUNT
```

The probe uses fixed representative symbols, two-bar/two-date requests, one
bounded snapshot or statement period, a spawned-worker per-call deadline, and
only the positive-list method plan. Its report contains SDK/Python/OS metadata,
method signatures, outer shapes, columns, dtypes, row counts, timings and
redacted typed outcome classes. It never writes credentials, session state or
licensed row values. Missing SDK, credentials, authentication, entitlement,
quota, schema, valid-empty and transient outcomes remain distinct.

## Licensed installation

Install the reviewed exact version in an isolated environment using the
official package index:

```text
python -m venv .venv-fiinquantx
. .venv-fiinquantx/bin/activate
python -m pip install --upgrade pip
python -m pip install matplotlib==3.10.9
python -m pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx==0.1.64
python -c "import importlib.metadata; print(importlib.metadata.version('fiinquantx'))"
```

Verify the wheel hash or equivalent integrity evidence and Python/OS
compatibility before use. The exact wheel imports `matplotlib` without declaring
it as an install dependency; install the pinned prerequisite first, as the
optional image build does. Do not use an unpinned mixed-index installation.

## Runtime configuration

Configure these values in the deployment environment, never in source,
fixtures, request parameters, logs, or responses:

```text
FIINQUANT_USERNAME=<licensed-account>
FIINQUANT_PASSWORD=<licensed-secret>
VNSTOCK_FIINQUANTX_SESSION_TTL=900
VNSTOCK_FIINQUANTX_ACQUIRE_TIMEOUT=30
```

Provider diagnostics expose SDK and credential readiness only; credentials are
never included in diagnostics.

The runtime caches one authenticated session for the configured TTL, allows one
provider request at a time, closes expired sessions on replacement, and clears
the cache after classified authentication/session failures. Rate-limit,
entitlement, quota, invalid-request, schema and transient failures are exposed
as stable typed errors without copying vendor response text.

For the local service image, set `VNSTOCK_INSTALL_FIINQUANTX=true` at build
time. The Docker Compose deployment publishes only `127.0.0.1:6900`.

## Bounded explicit-source examples

Use explicit `source=FIINQUANTX` only with bounded request windows and local
credentials that are never passed in the request payload:

```bash
vnalpha sync ohlcv \
  --symbols FPT \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --interval 1D \
  --source FIINQUANTX
```

```bash
curl -s "http://127.0.0.1:6900/v1/equity/ohlcv?symbol=FPT&start=2026-01-01&end=2026-01-31&interval=1D&source=FIINQUANTX" \
  | jq '.dataset, .meta.provider, .meta.source_method, .result[0] | {dataset:.}'
```

Explicit-source failures are also bounded examples:

```bash
vnalpha sync company-info \
  --symbol FPT \
  --source FIINQUANTX \
  --verbose
```

The command above fails as `unsupported_dataset_for_provider` and does not fall
back to another source.

## Storage policy

`vnalpha` accepts normalized FiinQuantX rows for warehouse-bound sync and
repair without a separate approval gate. Do not commit credentials, session
state, raw licensed payloads, or proprietary source to this repository.

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
`vnalpha sync membership --type index|sector --entity ENTITY --source
FIINQUANTX` persists one atomic observed snapshot. The snapshot header records
`SUCCESS` or valid `EMPTY`, observation time, request/correlation identity,
provider/SDK/contract/source-method lineage, and only allowlisted safe fields.
Member rows are keyed to that snapshot. The warehouse contract
does not expose these observations as official effective-date history.

FiinQuantX does not advertise `reference.symbols`, and a few index or sector
lists must never be combined into a synthetic full universe. Bootstrap
`symbol_master` and company/exchange/ICB reference from a separately approved
provider whose completeness has been verified for the deployment. The MVP1
candidate uses the existing VCI-backed `reference.symbols` contract for symbol,
exchange, company name and ICB fields, configured as
`OPENSTOCK_REFERENCE_SOURCE=VCI`. Use
`vnalpha sync symbols --source VCI --authoritative` only after a bounded current
completeness check is recorded for the candidate host; otherwise omit
`--authoritative` so unseen symbols are not deactivated. This mixed-provider
workflow preserves each provider in lineage rather than attributing the
reference universe to FiinQuantX.

A bounded Gate A operator sequence is therefore:

```text
OPENSTOCK_REFERENCE_SOURCE=VCI openstock-verify --mvp1
vnalpha sync symbols --source VCI [--authoritative]
vnalpha sync membership --type index --entity VN30 --source FIINQUANTX
vnalpha sync membership --type sector --entity <ICB_OR_ALIAS> --source FIINQUANTX
vnalpha sync ohlcv --symbols <BOUNDED_LIST> --start <DATE> --end <DATE> --source FIINQUANTX
vnalpha sync index --symbol VNINDEX --start <DATE> --end <DATE> --source FIINQUANTX
```

A successful offline unit test, a valid empty snapshot, or a historical live
probe does not prove current credentials, universe completeness, or the
semantics of a newly changed request.

For OHLCV, supported request modes are:

- `symbol`, `count_back` (1 to 10,000), `interval=1D`; or
- `symbol`, bounded `start` plus `end`, `interval=1D`.

`count_back` and date range are mutually exclusive. Open-ended date ranges are
rejected before session creation. The provider sends the bounded canonical
request policy (`adjusted=False`, `lasted=False`). FiinQuantX rows therefore
enter the shared OHLCV contract only with `basis=RAW_UNADJUSTED`; adjusted rows
are never selected under the same canonical warehouse key. Both raw and
canonical rows retain `price_basis=RAW_UNADJUSTED`; legacy FiinQuantX rows with
missing basis and any adjusted-basis rows fail closed in canonical validation.
Callers cannot override either SDK control. Output metadata records the exact
request controls, source method, SDK and contract versions, plus only the
verified raw-unadjusted basis. Unknown vendor columns are dropped before the
canonical response is returned.

Credentials must come from local environment or credential/configuration
abstractions. They must never be passed as dataset parameters or written to
logs, diagnostics, dataframes, service responses, or fixtures.
