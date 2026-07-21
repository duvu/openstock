# Proposal: Experience memory and governed learning

## Status

Proposed active change. No runtime capability is implied until implementation and exact-SHA validation are complete.

## Related

- Issue #346 — program epic/spec
- #306 — minimal quant research loop
- #317 — queue-backed provisioning and warehouse ownership
- #327 — provider-to-research data coverage
- #255 — live operational proof
- #260 — candidate-outcome lineage
- #262 — bounded replay/backtest

## Why

OpenStock already persists market evidence, deterministic research artifacts, evidence-backed memory claims and candidate outcomes. It can describe what is currently known about a symbol, sector or market and can mature some forward outcomes.

It cannot yet reconstruct and evaluate the complete learning chain:

```text
research request
→ resolved intent and point-in-time evidence
→ deterministic conclusion or prediction
→ observed user feedback and market outcome
→ policy/setup/regime evaluation
→ proposed improvement
→ governed promotion, rejection or rollback
```

Without this chain, memory remains primarily state-oriented. The system cannot answer reliably which conclusions it previously produced, whether they were correct, under which policy and regime they worked, or why a later policy version should replace an accepted version.

## Objective

Add a bounded experience and learning layer:

```text
Evidence
→ Semantic memory
→ Research episode
→ Prediction
→ Outcome
→ Evaluation
→ Learning candidate
→ Human-approved policy version
```

The system may collect experience, calculate evaluation evidence and propose candidate improvements. It must not autonomously modify accepted scoring, portfolio, intent or risk policies.

## Scope

### Experience ledger

Persist immutable research episodes and explicit predictions linked to exact:

- requested and effective dates;
- resolved intent and subjects;
- capability and requested enrichments;
- data/evidence snapshot hashes;
- policy and methodology versions;
- result status, limitations and artifact references.

### Feedback and outcomes

Persist typed user feedback separately from market truth. Link matured candidate and portfolio outcomes to explicit prediction records without rewriting the original episode.

### Evaluation

Create immutable evaluation runs sliced by policy, setup, regime, horizon and point-in-time universe. Initial metrics include sample size, hit rate, excess return, drawdown, favorable excursion, turnover/cost assumptions, calibration buckets and drift diagnostics.

### Governed learning

Persist learning candidates and immutable policy versions. Promotion requires reproducible replay/walk-forward or equivalent bounded validation plus explicit approval evidence. Rejection and rollback preserve history.

### User and portfolio context

Store only explicit user preferences as preference data, not market evidence. Link portfolio research runs to subsequent outcomes and attribution when portfolio research is available.

## Existing capability to reuse

- DuckDB evidence and research warehouse;
- current symbol/entity memory claims, lifecycle and compaction;
- candidate score/watchlist and outcome lineage;
- replay/backtest artifacts;
- queue-backed warehouse ownership and global write coordinator from #317/#343;
- optional portfolio research artifacts when delivered.

## Architecture boundaries

- Evidence and outcomes remain authoritative over memory summaries and LLM prose.
- Memory claims remain source-backed and lifecycle-managed.
- Research episodes are immutable historical records, not current truth projections.
- User preference, user action and user satisfaction are not market labels.
- LLMs may summarize evaluation or propose hypotheses, but cannot create ground truth, mutate policy or approve promotion.
- Historical evaluation must be point-in-time, cost-aware and reproducible.

## Compatibility and migration

Existing memory claims, candidate outcomes and replay artifacts remain valid. The first migration adds new append-oriented tables and optional linkage fields. Existing rows are not retroactively treated as predictions unless a deterministic reconstruction with sufficient lineage is possible; otherwise they remain legacy evidence.

## Delivery sequence

1. Experience ledger and prediction contracts.
2. Feedback and prediction-to-outcome linkage.
3. Evaluation runs and diagnostics.
4. Learning candidates and policy lifecycle.
5. Explicit user preferences and portfolio attribution.
6. Shared CLI/TUI/assistant read surfaces and evidence validation.

## Non-goals

- Broker, order or account execution.
- Autonomous policy promotion or online self-modification.
- Generic enterprise ML platform, external model registry or feature store.
- Kafka, event-sourcing infrastructure or distributed training.
- Vector database as a core dependency.
- Reinforcement learning, deep learning or continuous online retraining in the initial delivery.
- Treating generated prose as validated memory or training truth.
