# Proposal: Setup Historical Evidence Engine

## Summary

Define the OpenSpec for setup-specific historical evidence in OpenStock.

This is an OpenSpec-only change.

## Motivation

OpenStock already has outcome evaluation. The target system needs reusable evidence by setup cohort so analysis, shortlist, and scenario plans can say what happened historically under similar conditions.

Evidence must be empirical, caveated, and research-only.

## Scope

Define requirements for:

```text
/setup-evidence
setup_evidence_snapshot
cohort definitions
sample size
forward return distribution
FAE/AAE stats
outcome rate
regime split
small-sample caveats
assistant evidence tool
```

## Non-goals

- No guarantee of future return.
- No personalized recommendation.
- No trade execution.
- No curve-fitted strategy optimizer.

## Target output

```text
setup_type
sample_definition
horizon
sample_size
forward_return_distribution
fae_aae_stats
outcome_rate
regime_split
small_sample_caveat
lineage
```
