# Design: Setup Historical Evidence Engine

## Architecture

```text
candidate_score + setup_type + outcome tables + regime snapshots
  -> SetupCohortBuilder
  -> EvidenceCalculator
  -> SetupEvidenceSnapshot repository
  -> command/assistant/TUI output
```

## Proposed modules

```text
vnalpha/research_intelligence/setup_evidence.py
vnalpha/research_intelligence/cohorts.py
vnalpha/research_intelligence/evidence_metrics.py
vnalpha/commands/handlers/setup_evidence.py
```

## Cohort definitions

MVP cohorts may include:

```text
setup_type
score bucket
risk flag presence
market regime
sector strength bucket
horizon
```

## Metrics

```text
sample_size
median_forward_return
mean_forward_return
percentile_distribution
positive_outcome_rate
max_favorable_excursion
max_adverse_excursion
regime_split
small_sample_flag
```

## Command contract

```text
/setup-evidence SETUP_TYPE [--horizon N] [--date YYYY-MM-DD] [--regime REGIME]
/setup-evidence SYMBOL [--date YYYY-MM-DD]
```

## Assistant tool

```text
evidence.get_setup_history
```

## Caveats

Every output must include:

```text
sample-size caveat
historical-not-predictive caveat
methodology version
data quality caveat when relevant
```
