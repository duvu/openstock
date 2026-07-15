# Provider hardening

The provider-hardening layer makes source selection and provider output observable, testable and fail-closed before data reaches downstream research.

Primary modules live under:

```text
vnstock/vnstock/core/provider/
vnstock/vnstock/core/contracts/
vnstock/vnstock/core/auth/
```

## Current architecture

```text
canonical dataset request
→ PluginRegistry.providers_for(dataset)
→ PluginRouter selection by explicit source, capability, auth and health
→ PluginRuntime.fetch()
→ provider validation and allowlisted fetch
→ provider-specific normalization
→ DatasetContract validation
→ DataResult with quality, diagnostics, latency and routing lineage
```

`PluginRuntime` is the canonical synchronous service execution path. Public/service code must not call a provider SDK directly.

## Current status

| Component | Current state |
|---|---|
| Provider protocol and instance registry | Implemented |
| Canonical dataset contracts | Implemented for the accepted initial dataset set and selected later reference contracts |
| Auth-aware routing | Implemented |
| Health-aware routing and cooldown | Implemented in `PluginRouter` |
| Explicit-source no-silent-fallback behavior | Implemented |
| `PluginRuntime` result/diagnostic path | Implemented |
| Schema-drift detection | Implemented |
| OHLCV cross-provider comparison | Implemented |
| Provider health scoring | Implemented |
| Capability matrix | Implemented |
| Synthetic offline contract tests | Implemented |
| Opt-in live smoke tests | Implemented |
| Price-board/intraday comparison | Planned |
| First-class reference/fundamental quality rules | Incomplete |
| Provider-level persistent quota/rate accounting | Incomplete; provider-specific bounded controls may exist |
| Streaming/WebSocket runtime | Not part of synchronous `PluginRuntime` |

Older text stating that runtime routing is still round-robin is obsolete. `PluginRouter` now performs health- and auth-aware selection; legacy registries may still exist for backward-compatible public UI dispatch.

## Registered providers

| Provider | Main supported use | Status notes |
|---|---|---|
| KBS | Vietnam equity/index OHLCV, quote, intraday, reference and fundamental paths | Primary public provider |
| VCI | Vietnam equity/index OHLCV, quote, intraday, industry and index data | Stable secondary provider |
| DNSE | Vietnam equity OHLCV and quote | Geographic/auth availability constraints may apply |
| TCBS | Equity market/reference/fundamental paths | Experimental, unofficial endpoints may drift |
| MSN | Selected global/search and OHLCV use cases | Experimental |
| FMP | Authenticated global market/fundamental data | Requires API key |
| FMARKET | Fund NAV and fund information | Fund-only provider |
| FIINQUANTX | Bounded licensed daily equity/index OHLCV and current index/sector membership snapshots | Experimental, explicit source only, exact SDK/credentials/license acknowledgement required |

The current FiinQuantX implementation is not a general replacement for public providers. It remains limited to capabilities with runtime evidence, and issues #105/#106 own the unresolved commercial, session, entitlement/quota, company-reference and closure work.

SSI and ABS are discovery candidates, not implemented providers.

## Capability declarations

Every provider capability must declare at least:

```text
supported
status
requires authentication
dataset
asset type
supported intervals or query shape
known limitations
```

A capability declaration is not sufficient proof. It must match:

- the implemented provider handler;
- canonical contract and normalizer;
- synthetic fixture and contract test;
- bounded live evidence where the source can be tested safely;
- current license and entitlement policy for commercial providers.

Unsupported or unresolved datasets must fail as typed unsupported/access outcomes rather than appearing as valid empty data.

## Routing semantics

### Explicit source

```text
source="FIINQUANTX"
```

or any other explicit source means:

- use that provider if it is implemented and usable;
- otherwise return a typed installation/auth/access/cooldown/schema/provider failure;
- never silently return another provider's data.

### Automatic source

Auto routing considers:

- dataset capability;
- auth policy;
- provider health and cooldown;
- configured priority;
- availability/freshness evidence;
- provider-specific policy such as commercial acknowledgement and bounded request limits.

The routing decision records selected and rejected candidates with sanitized reasons.

## Schema drift

Drift detection checks normalized output against the registered schema baseline. Important outcomes include:

```text
invalid input
missing baseline
missing required column
dtype mismatch
unexpected null
unexpected row-count shape
```

Unknown provider field casing, timestamp representation, units or response objects must not be guessed. Versioned provider normalizers should fail closed or return a degraded typed result according to the dataset contract.

## Cross-provider comparison

OHLCV comparison evaluates:

- common date coverage;
- missing-date gaps;
- price-scale divergence;
- volume divergence;
- symbol/interval/request identity.

Comparison diagnostics are evidence. They do not silently rewrite one provider to match another. Adjusted versus unadjusted data must be declared before values are considered comparable.

## Provider health

Health is derived from collected evidence such as:

```text
latency
error rate
schema status
freshness status
warning/error diagnostics
consecutive failures
cooldown state
```

A successful fetch records success; provider/runtime failures record failure. Health affects automatic routing but explicit-source requests preserve their named-provider semantics subject to disabled/cooldown policy.

## Offline and live tests

Offline provider contract tests use synthetic fixtures:

```text
tests/contracts/providers/
tests/fixtures/providers/
```

Live tests are disabled by default:

```bash
VNSTOCK_LIVE_TESTS=true PYTHONPATH=. pytest tests/live/providers -m live -v
```

Licensed tests require provider-specific acknowledgement and credentials. They must use bounded requests and log only safe shapes, counts, hashes, versions and statuses—never secrets or raw licensed rows.

## Provider onboarding gate

A new provider or dataset is not complete until it has:

1. explicit data-only scope;
2. an official or otherwise reviewed access contract;
3. positive allowlist excluding broker/account/execution members;
4. parameter validation before provider I/O;
5. canonical field/unit/time semantics;
6. a provider normalizer and dataset contract;
7. truthful empty/partial/failure outcomes;
8. capability and routing integration;
9. synthetic fixtures and contract tests;
10. bounded live evidence where permitted;
11. secret redaction and safe diagnostics;
12. license/persistence/exposure decisions for commercial data;
13. documentation and GitHub issue closure evidence.

## Permanent boundary

The provider platform remains within the **read-only research boundary**. Credentialed data access is permitted only for approved data providers. Broker login, account information, buying power, loans, orders, positions, portfolio mutation, allocation, margin, transfers and trading execution are prohibited even if a vendor SDK exposes them.