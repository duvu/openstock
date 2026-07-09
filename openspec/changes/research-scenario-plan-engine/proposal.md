# Proposal: Research Scenario Plan Engine

## Summary

Define the OpenSpec for conditional research scenario plans in OpenStock.

This is an OpenSpec-only change.

## Motivation

The target OpenStock system should help users structure research around conditional scenarios without crossing into trading execution.

A scenario plan is not a buy/sell plan. It is a research artifact that summarizes current setup, key levels, confirmation conditions, invalidation conditions, caveats, and checklist items for future review.

## Scope

Define requirements for:

```text
/research-plan SYMBOL
research_scenario_plan artifact
key levels
confirmation conditions
invalidation conditions
scenario tree
research checklist
rough risk/reward estimate as caveated research context
policy classification
assistant scenario tool and intent
```

## Non-goals

- No order instruction.
- No position sizing.
- No portfolio allocation.
- No broker/account integration.
- No live strategy deployment.

## Target output

```text
symbol
current_setup
key_levels
confirmation_conditions
invalidation_conditions
scenario_tree
risk_reward_estimate
checklist
confidence
caveats
research_only_language
```
