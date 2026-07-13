# Design: Research Intelligence Data Model Foundation

## Purpose

Provide a common schema and repository layer for all higher-order research intelligence workflows.

The data model must support:

```text
commands -> deterministic tools -> assistant synthesis -> TUI rendering -> evaluation -> closed-loop repair
```

## Principles

- Persist research objects as structured data, not only prose.
- Keep artifacts reproducible and lineage-aware.
- Use correlation IDs to link commands, assistant turns, sandbox jobs, repair bundles, and validation reports.
- Keep all outputs research-only and caveated.
- Never add broker/order/account/portfolio/margin/trading execution fields.

## Proposed package boundary

```text
vnalpha/research_models/
  __init__.py
  models.py
  repositories.py
  validators.py
  migrations.py or warehouse migration entries
  contracts.py
```

## Core objects

### MarketRegimeSnapshot

Fields:

```text
as_of_date
regime_state
index_trend
index_volatility
breadth_summary
sector_strength_ref
freshness
lineage
methodology_version
correlation_id
```

### SectorStrengthSnapshot

Fields:

```text
as_of_date
sector
rank
relative_performance
rotation_state
breadth_proxy
member_count
methodology_version
lineage
quality_status
```

### SymbolLevelSnapshot

Fields:

```text
symbol
as_of_date
support_levels
resistance_levels
pivot_levels
level_strength
source_bar_refs
methodology_version
lineage
quality_status
```

### SetupAnalysis

Fields:

```text
symbol
as_of_date
setup_type
setup_quality
trend_context
momentum_context
relative_strength_context
volume_context
volatility_context
level_snapshot_ref
confidence
caveats
lineage
```

### ShortlistCandidate

Fields:

```text
shortlist_run_id
rank
symbol
setup_type
setup_quality
shortlist_score
why_shortlisted
why_restrained
confirmation_conditions
invalidation_conditions
risk_context
lineage
```

### ResearchScenarioPlan

Fields:

```text
scenario_plan_id
symbol
as_of_date
current_setup
key_levels
scenario_tree
confirmation_conditions
invalidation_conditions
checklist
risk_reward_estimate
confidence
caveats
policy_classification
```

### SetupEvidenceSnapshot

Fields:

```text
setup_type
sample_definition
as_of_date
horizon
sample_size
forward_return_distribution
fae_aae_stats
outcome_rate
regime_split
small_sample_caveat
lineage
```

### ResearchAnswerAudit

Fields:

```text
answer_audit_id
assistant_session_id
research_session_id
intent
tools_used
artifact_refs
dataset_freshness
groundedness_result
policy_result
missing_data
caveats
created_at
correlation_id
```

## Storage strategy

Implementation may use DuckDB tables plus file artifact references.

Large outputs should be stored as artifacts and referenced by path or artifact ID.

## Validation

Every object should validate:

```text
required IDs
as_of_date
lineage
quality_status where applicable
methodology_version
correlation_id
research-only policy constraints
```

## Migration strategy

Migrations must be additive and idempotent.

No existing table should be repurposed in a way that breaks current `/scan`, `/explain`, `/compare`, `/quality`, `/lineage`, `/note`, or assistant flows.
