# Proposal: Research Answer Evaluation Golden Set

## Summary

Define the OpenSpec for evaluating OpenStock research answers, scenario plans, and policy behavior with golden sets.

This is an OpenSpec-only change.

## Motivation

As OpenStock adds deeper assistant and research-intelligence workflows, quality must be tested beyond unit tests. The system needs golden sets for groundedness, caveats, missing-data disclosure, policy safety, and research-only wording.

## Scope

Define requirements for:

```text
golden research answer cases
golden scenario plan cases
golden policy refusal cases
groundedness checks
artifact reference checks
small-sample caveat checks
no personalized recommendation checks
CI command
```

## Non-goals

- No subjective stock recommendation scoring.
- No optimization for a specific trading outcome.
- No live market prediction benchmark.

## Target evaluation families

```text
research_answer_groundedness
scenario_plan_policy_safety
historical_evidence_caveats
shortlist_research_only_wording
missing_data_disclosure
artifact_reference_integrity
```
