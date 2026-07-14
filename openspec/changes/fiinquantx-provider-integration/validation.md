# Validation: FiinQuantX Provider Integration

## Status

```text
OpenSpec authored: yes
Licensed SDK contract discovery: not started
Runtime implementation: not started
Offline validation: not run
Licensed live validation: not run
Phase gates: pending
```

This file is the evidence ledger. No task or phase gate may be checked from proposal text, marketing material, an installed wheel, or a PR description alone.

## Source review evidence

| Source | Reviewed state | Verified result |
|---|---|---|
| `https://github.com/fiinquant/fiinquantx` | `main` at `abb1e038f3e7401ab770067c5d7a539a06823097` | Public repository exists and is maintained by the `fiinquant` organization. |
| `README.md` | reviewed | Contains the project name only; no public API/auth/schema contract. |
| `docs/simple/fiinquantx/index.html` | reviewed | PEP-503-style package index linking release wheels. |
| package index | reviewed | Newest listed wheel at review time is `fiinquantx-0.1.64-py3-none-any.whl`. |

## Evidence rules

- Record the exact OpenStock commit tested.
- Record the exact FiinQuantX SDK version tested.
- Record Python version and operating system.
- Do not attach credentials or raw licensed production payloads.
- Synthetic fixtures must include a provenance note confirming they contain no licensed values.
- Live-test output must include only safe counts, schemas, statuses, and hashes.
- Mark commands `not run`, `passed`, `failed`, `skipped`, or `inconclusive`; do not infer success.
- A capability cannot be enabled from introspection alone; it requires an approved mapping and contract test.

## Discovery ledger

| Timestamp | OpenStock SHA | SDK version | Discovery item | Result | Evidence |
|---|---|---|---|---|---|
| pending | pending | pending | installation/import contract | not run | pending |
| pending | pending | pending | auth/session contract | not run | pending |
| pending | pending | pending | entitlement/quota contract | not run | pending |
| pending | pending | pending | dataset/method matrix | not run | pending |
| pending | pending | pending | field/unit/timezone matrix | not run | pending |
| pending | pending | pending | fundamentals publication/restatement matrix | not run | pending |
| pending | pending | pending | license and persistence decision | not run | pending |

## Required focused validation

Expected implementation commands, adjusted only when actual test paths are created:

```bash
cd vnstock

PYTHONPATH=. pytest -q \
  tests/unit/providers/fiinquantx \
  tests/contracts/providers/test_fiinquantx_contract.py

PYTHONPATH=. pytest -q \
  tests/unit/core/provider \
  tests/unit/core/auth \
  tests/contracts/providers
```

Required cases include:

```text
SDK absent
SDK incompatible
valid authentication
invalid/expired authentication
entitlement available/unavailable
quota and rate-limit outcomes
explicit-source no-fallback behavior
auto-source routing decision
valid empty dataset
invalid symbol and interval
schema drift
canonical normalization
metadata and secret redaction
publication-time missing/present
financial restatement
provider runtime path
base-package import without SDK
```

## Required repository validation

```bash
cd vnstock
ruff check .
ruff format --check .
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
cd ..
openspec validate fiinquantx-provider-integration --strict
```

If provider-specific service tests are added, they must be included in the full offline command before G6 is checked.

## Licensed live validation

Live validation is opt-in and must use a minimal bounded request set:

```bash
cd vnstock
VNSTOCK_LIVE_TESTS=true \
VNSTOCK_LIVE_PROVIDERS=FIINQUANTX \
VNSTOCK_FIINQUANTX_LICENSED=true \
PYTHONPATH=. pytest -q tests/live/providers/test_fiinquantx_live.py -m live
```

Live evidence must record:

- SDK version;
- safe authenticated/entitled state;
- datasets exercised;
- symbols/date ranges without raw rows;
- row counts and canonical columns;
- quality and routing status;
- quota impact where safely available;
- whether any licensed payload was persisted.

## Cross-provider evidence

For overlapping market datasets, attach bounded comparison output against approved providers:

```text
common dates
coverage gaps
price-scale divergence
volume/value unit divergence
symbol mapping
adjustment-state difference
freshness difference
```

Differences must remain typed diagnostics. Validation must not silently rewrite one provider to match another.

## Packaging evidence

Two packaging environments are required:

1. Base environment without FiinQuantX:
   - import `vnstock` succeeds;
   - default registry construction succeeds;
   - FiinQuantX reports not installed/unavailable safely;
   - package build succeeds.
2. Licensed environment with the approved SDK version:
   - provider registers;
   - auth/entitlement diagnostics work;
   - approved contract tests and bounded live tests pass.

## Phase-gate ledger

| Gate | Exact commit | Result | Evidence |
|---|---|---|---|
| G0 licensed discovery | pending | not run | pending |
| G1 provider foundation | pending | not run | pending |
| G2 reference/EOD market | pending | not run | pending |
| G3 market structure/foreign flow/valuation | pending | not run | pending |
| G4 publication-aware fundamentals | pending | not run | pending |
| G5 optional intraday/vendor indicators | pending | not run | pending |
| G6 full regression/package/live/OpenSpec | pending | not run | pending |