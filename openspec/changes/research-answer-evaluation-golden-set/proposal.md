# Proposal: Research Answer Evaluation Golden Set

## Summary

Define and implement the initial vnalpha evaluation-fixture boundary for assessing
OpenStock research answers, scenario plans, and policy behavior with golden sets.

This change establishes typed local golden-case schemas and YAML loading only. It
does not yet implement evaluation checks, a runner, reporting, CLI commands, CI
integration, documentation, or seed cases.

## Motivation

As OpenStock adds deeper assistant and research-intelligence workflows, quality must be tested beyond unit tests. The system needs golden sets for groundedness, caveats, missing-data disclosure, policy safety, and research-only wording.

## Scope

Define executable requirements for:

```text
typed golden research answer cases
typed golden scenario plan cases
typed golden policy refusal cases
typed historical evidence cases
typed shortlist cases
strict YAML fixture loading with local artifact-reference fields
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
