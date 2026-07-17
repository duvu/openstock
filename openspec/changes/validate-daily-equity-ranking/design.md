## Context

GitHub epic #196 defines ten dependent delivery issues. Existing feature snapshots
emit `EXACT_DATE`, `STALE_DATE`, or `MISSING_BENCHMARK`, while research automation
accepts `good|ok|pass`. Existing hypotheses also read `feature_snapshot.return_20d`
instead of the append-only later-observation store.

## Goals / Non-Goals

**Goals:**

- Keep one typed point-in-time eligibility contract across builders and consumers.
- Keep feature inputs, later outcomes, price basis, policies, assumptions, reports,
  ranking snapshots, and decisions independently versioned and reproducible.
- Preserve truthful partial and failed states with typed exclusions.
- Keep all operator decisions manual and all product behavior research-only.

**Non-Goals:**

- Trading execution, broker or account integration, allocation, optimization,
  online learning, unrestricted parameter search, or LLM-selected policies.

## Decisions

### One feature eligibility boundary

Only production `EXACT_DATE` snapshots are eligible for point-in-time research.
Stale, missing-benchmark, null, and unknown legacy statuses are readable but
excluded with typed reasons. Consumers persist the contract version in lineage.

### Later outcomes are separate measurements

Feature columns remain event-time inputs. Hypotheses and evaluators join by symbol
and event/watchlist date to complete later observations and persist the measurement
contract, horizon, status, and source. Missing outcomes remain explicit.

### Immutable policy and snapshot identity

Scoring policies, assumption policies, ranking batches, report specifications,
dataset experiments, and policy decisions receive deterministic payload hashes.
Finalized historical content is append-only; rollback changes active pointers only.

### Dependency-ordered delivery

Implementation follows `#197 -> (#198, #199) -> #200 -> #201 -> #202 -> #203 ->
(#204, #205) -> #206`. Each issue receives focused, full-suite, surface, packaging,
strict OpenSpec, and exact-SHA CI evidence before closure.

## Risks / Trade-offs

- Fail-closed eligibility reduces usable historical samples.
- Append-only identities add schema and migration work.
- Forward observations require elapsed market time and may block acceptance.
- Valid evaluation may reject the current score or a licensed dataset extension.

## Migration Plan

Legacy rows remain queryable but are ineligible until rebuilt or explicitly mapped
by a versioned migration. New policy and snapshot records are additive. No historical
score, ranking, outcome, or decision is rewritten during migration.
