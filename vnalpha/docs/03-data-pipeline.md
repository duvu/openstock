# 03. Data pipeline

> **Status:** current implementation contract.
>
> Dataset priority and delivery order are maintained in [GitHub issue #238](https://github.com/duvu/openstock/issues/238). The
> current queue-backed provisioning successor is [#317](https://github.com/duvu/openstock/issues/317). This document describes the stable ingestion, validation and lineage boundaries.

## Core rule

```text
No anonymous or unvalidated provider frame may enter research computation.
```

`vnalpha` consumes provider-independent responses from `vnstock-service`. It
must not import commercial SDKs, call provider-specific endpoints or introduce a
research-layer fallback adapter when a dataset is missing.

## Current data flow

```text
vnstock-service request
→ typed per-symbol outcome and safe provider metadata
→ ingestion_run
→ market_ohlcv_raw
→ validation and ohlcv_quarantine
→ canonical_ohlcv
→ feature_snapshot + relative_strength_snapshot
→ scoring, market/sector context, outcomes and research artifacts
```

Reference-data flow additionally preserves symbol source snapshots, membership
and point-in-time classification history before updating `symbol_master`.

Corporate-action flow is separate from OHLCV promotion:

```text
vnstock reference.corporate_actions
→ corporate_action_raw_evidence
→ validation + corporate_action_quarantine
→ immutable corporate_action revisions + source links
→ corporate_action_affected_range
```

KBS and VCI feeds are recorded as `MARKET_DATA_PROVIDER` evidence, not official
issuer disclosures. This pipeline does not calculate adjusted prices; #113 owns
factor and adjusted-series derivation.

## Storage layers

### Ingestion evidence

`ingestion_run` records the requested universe, source, parameters, correlation
ID, terminal status and per-symbol SUCCESS/EMPTY/FAILED/INVALID/SKIPPED outcomes.
A partial batch must remain partial; aggregate success cannot hide symbol-level
failure.

`market_ohlcv_raw` stores the bounded response associated with one ingestion run
and retains provider, quality, diagnostics and fetch-time evidence.

### Validation and quarantine

Invalid OHLCV observations are written to `ohlcv_quarantine` with:

- provider and ingestion run;
- affected symbol/time/interval;
- rule IDs and validation version;
- bounded invalid-value evidence;
- first/last detection and resolution reference.

An unresolved quarantined observation cannot be promoted or silently used by
research consumers.

### Canonical OHLCV

`canonical_ohlcv` is the only price input for features, scoring, context and
research studies. Each row preserves selected provider, quality status and
source run lineage.

Canonical promotion is validation-first. Provider preference cannot override a
failed quality gate.

### Symbol identity and taxonomy

Current contracts include:

```text
symbol_master
symbol_source_snapshot
symbol_source_membership
symbol_classification_history
```

Authoritative symbol reconciliation is allowed only for completed, error-free
source snapshots. Historical research must use the classification observable at
the requested date, not the latest sector or lifecycle value.

### Feature evidence

`feature_snapshot` persists calculated values together with:

- exact source and benchmark bar dates;
- observed and required history;
- feature profile;
- neutral completeness;
- relative-strength completeness;
- missing-field evidence;
- build and rule versions;
- lineage.

The profile registry currently distinguishes `MINIMAL_20`, `STANDARD_120` and
`FULL_252`. Consumers declare the profile they need. Row existence alone is not
a readiness contract.

`relative_strength_snapshot` stores benchmark-specific horizons and methodology
lineage. Compatibility fields versus VNINDEX remain transitional; new consumers
must preserve the actual benchmark identity.

## Incremental sync and gap handling

Daily operation is watermark- and session-aware:

```text
vnalpha data sync daily
vnalpha data gaps SYMBOL
vnalpha data repair ohlcv SYMBOL
```

The pipeline distinguishes:

- expected non-trading dates;
- provider-valid empty responses;
- missing sessions;
- unresolved invalid observations;
- stale or incomplete feature evidence.

Repairs are bounded by symbol, interval and date range. They preserve correlation
and resolution references and must be idempotent.

## Canonical command surface

Typical explicit workflow:

```bash
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
vnalpha sync index --symbol VNINDEX --start 2024-01-01
vnalpha sync corporate-actions SSI --start 2024-01-01 --source VCI
vnalpha data status corporate-actions SSI
vnalpha build canonical
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
```

These direct commands and the Compose worker are explicit development or
recovery tools. Normal single-host maintenance first freezes and enqueues a
session, then lets the one provisioner process it:

```bash
vnalpha maintain enqueue --date today
vnalpha jobs health
```

The weekday producer timer invokes that enqueue operation; it never runs a
competing one-shot worker. The long-running `openstock-provisioner.service`
owns `/var/lib/openstock/queue/provisioning.sqlite3` and the queue lock. Do not
run the Compose worker beside that service.

For explicit recovery only, use the same commands through the root Compose
worker:

```bash
docker compose --profile job run --rm vnalpha-worker sync symbols
docker compose --profile job run --rm vnalpha-worker build canonical
docker compose --profile job run --rm vnalpha-worker build features --date today
```

Module-level `python -m vnalpha.<implementation module>` commands are not a
public interface and must not be documented as the normal operational path.

## Quality and readiness semantics

Research boundaries fail closed when required evidence is:

- missing;
- stale for the requested date;
- invalid or quarantined;
- based on an unsupported/legacy feature profile;
- missing required benchmark-relative strength;
- inconsistent with provider persistence policy.

Optional context may be disclosed as missing without blocking an unrelated
capability. For example, benchmark-neutral breadth can use neutral feature
evidence while sector strength and scoring require complete relative-strength
evidence.

## Point-in-time guarantees

Historical datasets must not use future:

- symbol membership or lifecycle status;
- sector classifications;
- corporate publications;
- corporate actions or adjusted-price factors;
- feature rows or benchmark observations;
- repair outcomes that were not observable at the research date.

The future Backtest Lab consumes these contracts; it must not create a second,
less strict ingestion path.

## Extension rule

A new dataset begins in `vnstock` with a provider-independent capability and
canonical contract. It enters `vnalpha` only after:

1. access and commercial policy are reviewed;
2. parameters and schema are canonicalized;
3. empty, partial and failure outcomes are typed;
4. validation and provenance are defined;
5. fixtures and bounded evidence exist;
6. persistence policy is explicit.
