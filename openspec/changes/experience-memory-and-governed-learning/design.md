# Design: Experience memory and governed learning

## Design goals

1. Preserve exact research experience without turning all history into current memory.
2. Link explicit predictions to observed outcomes deterministically.
3. Evaluate policies by point-in-time slices and costs rather than anecdotes.
4. Allow the system to propose improvements without autonomously changing accepted behavior.
5. Reuse the existing modular monolith, DuckDB warehouse, memory lifecycle, outcomes and replay engine.

## Conceptual model

OpenStock SHALL distinguish five forms of retained state:

```text
Evidence memory    raw, canonical and derived research evidence
Semantic memory    source-backed claims and current projections
Episodic memory    immutable records of research requests and results
Outcome memory     realized observations linked to predictions
Procedural memory  immutable policy and methodology versions
```

These forms have different authority and lifecycle. A research episode records what the system concluded at a point in time; it does not become a current fact merely because it was recorded.

## High-level flow

```text
Data and evidence plane
    ↓
Research application plane
    ↓
Experience ledger
    ↓
Prediction/outcome linkage
    ↓
Evaluation plane
    ↓
Learning candidate plane
    ↓
Governed policy lifecycle
```

## Component ownership

### Research applications

Current-symbol, watchlist, portfolio and future research applications SHALL create an episode only after the request has a stable normalized contract and a terminal protocol result. They SHALL expose exact artifact and policy references rather than duplicating the analysis logic in the learning subsystem.

### Experience ledger

Owns append-oriented records:

- `research_episode`;
- `prediction_record`;
- `decision_feedback`.

The ledger records historical execution context. It does not decide whether a prediction was correct.

### Outcome linker

Owns deterministic links between mature persisted outcomes and prediction records. It reuses existing candidate/portfolio outcomes and never fabricates labels from narrative text.

### Evaluation service

Builds immutable `evaluation_run` artifacts from linked predictions and outcomes. It owns aggregation, calibration, regime slices, sample-size diagnostics, transaction-cost assumptions and drift evidence.

### Learning candidate service

Creates immutable `learning_candidate` proposals from explicit experiment specifications. It may use deterministic searches or LLM-assisted hypotheses, but the proposal must identify exact parent policy, changed parameters, training/evaluation evidence and non-goals.

### Policy registry

Owns immutable `policy_version` records and status transitions:

```text
DRAFT
→ EXPERIMENTAL
→ ACCEPTED
→ RETIRED

DRAFT|EXPERIMENTAL → REJECTED
ACCEPTED → RETIRED or explicit rollback to a prior accepted version
```

No evaluation service or LLM may transition a policy to `ACCEPTED` without explicit approval evidence.

## Data contracts

### `research_episode`

Minimum fields:

```text
episode_id
session_id
surface
intent_goal
subjects_json
requested_date
effective_date
request_hash
requested_capability
effective_capability
requested_enrichments_json
data_snapshot_hash
policy_refs_json
result_status
analysis_artifact_ref
limitations_json
correlation_id
created_at
```

Episodes are immutable. Corrections produce linked feedback or a later superseding research episode; they do not rewrite history.

### `prediction_record`

Minimum fields:

```text
prediction_id
episode_id
subject_type
subject_id
prediction_type
target_definition_json
horizon_sessions
direction
score
confidence_bucket
benchmark_id
policy_id
policy_version
evidence_refs_json
status
created_at
```

Initial prediction types are finite:

```text
CANDIDATE_SELECTION
BENCHMARK_OUTPERFORMANCE
RISK_WARNING
SETUP_CLASSIFICATION
PORTFOLIO_INCLUSION
```

A score is not automatically a probability. Calibration is derived only by later evaluation.

### `decision_feedback`

Minimum fields:

```text
feedback_id
episode_id
feedback_type
subject_type
subject_id
value_json
reason
source
observed_at
```

Initial feedback types:

```text
WATCH
IGNORE
SAVE_RESEARCH
USER_CORRECTION
PAPER_PORTFOLIO_ADD
PAPER_PORTFOLIO_REMOVE
```

User feedback remains separate from outcome observations.

### `evaluation_run`

Minimum fields:

```text
evaluation_run_id
as_of_date
policy_id
policy_version
prediction_type
training_window_json
test_window_json
universe_hash
method_version
cost_model_version
metrics_json
slice_metrics_json
sample_counts_json
source_refs_json
status
created_at
```

Evaluation runs are immutable. A corrected outcome or method version creates a new run.

### `learning_candidate`

Minimum fields:

```text
candidate_id
candidate_type
parent_policy_id
parent_policy_version
proposed_config_json
experiment_spec_json
training_evidence_refs_json
evaluation_refs_json
rationale
status
created_at
```

Candidate types begin with explainable bounded changes:

```text
THRESHOLD_CHANGE
WEIGHT_CHANGE
CONSTRAINT_CHANGE
REGIME_RULE_CHANGE
```

### `policy_version`

Minimum fields:

```text
policy_id
version
policy_type
parent_version
content_hash
config_json
status
effective_from
effective_until
promotion_evidence_ref
approval_ref
rollback_reason
created_at
```

## Episode creation boundary

An episode SHALL be persisted only when:

1. input normalization and intent resolution succeeded;
2. requested/effective dates and capability are known;
3. a terminal protocol result exists;
4. referenced evidence and policy identities are stable;
5. the result is not merely an intermediate queue state unless the episode explicitly records a pending/accepted request with no prediction.

`ACCEPTED` and `PENDING` episodes may be recorded for operational analysis but SHALL NOT create market predictions until a deterministic analysis result is produced.

## Prediction extraction

Prediction records SHALL be created by deterministic adapters from typed research artifacts. The synthesizer or rendered prose is never parsed as the primary prediction source.

Examples:

- candidate score adapter emits candidate selection/setup/risk records;
- current-symbol result adapter emits benchmark-outperformance only when the application contract contains such a typed claim;
- portfolio run adapter emits portfolio-inclusion records for target weights under a named policy.

## Outcome linkage

The linker SHALL match by explicit prediction type, subject, as-of date, horizon, benchmark, policy and evidence lineage. Ambiguous or missing matches remain unlinked with a stable reason.

Original predictions and outcomes remain immutable. Link rows may be superseded when a source outcome revision is invalidated, but prior linkage history is retained.

## Evaluation methodology

Initial evaluation SHALL support:

- count and coverage;
- directional hit rate;
- median/mean realized and excess return;
- maximum drawdown and favorable excursion;
- calibration by score/confidence bucket;
- setup, sector and market-regime slices;
- turnover and cost-adjusted metrics where applicable;
- drift versus prior accepted evaluation window.

Every metric SHALL expose sample count and missing-data caveats. No policy comparison may claim superiority from a configured minimum-insufficient sample.

## Learning proposal flow

```text
Evaluation evidence
→ explicit experiment specification
→ learning candidate
→ replay/walk-forward or bounded challenger evaluation
→ comparison report
→ manual approve/reject
→ immutable policy version/status transition
```

The first delivery SHALL favor threshold, weight and constraint proposals over opaque model training.

## User preference boundary

Explicit user preferences SHALL be stored separately from market evidence and policy evaluation. Suggested fields:

```text
preference_key
value_json
source = EXPLICIT_USER
effective_from
updated_at
```

The system SHALL NOT infer or increase risk tolerance from observed clicks, watchlists or accepted suggestions without explicit confirmation.

## Portfolio learning boundary

When portfolio research exists, `portfolio_run` and realized portfolio evaluation may feed the same evaluation framework. Attribution SHALL separate selection, weighting, sector exposure, risk-control and turnover/cost effects when supported.

Target portfolio weights are research scenarios, not executed holdings. Paper or user-supplied portfolio snapshots must be labeled explicitly.

## Integration with maintenance and queue

Daily finalization may:

- create eligible research episodes for deterministic daily artifacts;
- mature and link outcomes;
- refresh bounded evaluation aggregates.

Heavy experiment generation or policy comparison remains an explicit command/application operation in the first delivery. No new distributed execution system is required.

All DuckDB writes use the global write coordinator from #343. The existing queue may be used for bounded long-running jobs only when a later implementation issue proves the need; this spec does not introduce a fourth generic queue goal.

## LLM boundary

LLMs MAY:

- summarize evaluation runs;
- propose hypothesis text and bounded experiment specifications;
- explain champion/challenger differences;
- classify explicit user corrections.

LLMs MUST NOT:

- create market outcome labels;
- convert their own prose into validated evidence;
- mutate accepted policy configuration;
- approve or promote a policy;
- hide adverse evaluation slices or insufficient sample warnings.

## Retrieval

Core learning retrieval SHALL use typed SQL filters and structured slices first:

```text
setup
regime
sector
score bucket
volatility bucket
horizon
policy version
```

Vector retrieval is optional for notes and narrative documents and is not required for the learning loop.

## Failure and recovery

- Missing episode lineage prevents prediction creation.
- Ambiguous outcome linkage fails closed.
- Failed evaluation persists no partial success artifact unless status is explicitly `PARTIAL` with exact missing slices.
- Policy transition failures leave the previous accepted policy unchanged.
- Rollback creates a new governed transition/reference; it never deletes the failed version.

## Security and research boundary

The learning layer remains research-only. It contains no broker credentials, order placement, account mutation or autonomous execution. User notes and external text remain untrusted data.
