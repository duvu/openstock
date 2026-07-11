# Design: Research Answer Evaluation Golden Set

## Architecture

```text
golden YAML/JSON cases
  -> evaluation runner
  -> assistant/command fixture execution
  -> groundedness checks
  -> policy checks
  -> artifact checks
  -> CI report
```

## Proposed layout

```text
vnalpha/evals/
  goldens/
    research_answers/*.yaml
    scenario_plans/*.yaml
    policy_refusals/*.yaml
    historical_evidence/*.yaml
    shortlist/*.yaml
  runner.py
  checks.py
  report.py
```

## Golden case fields

```text
case_id
input
expected_intent
required_tools
required_fields
forbidden_phrases
required_caveats
required_artifact_refs
missing_data_expectation
policy_expectation
```

## Checks

```text
groundedness: claims must be supported by tool payloads
policy: no execution instruction
caveats: required caveats are present
missing_data: missing data is disclosed
artifact_integrity: referenced artifacts exist
```

## Commands

```text
make eval-research-answers
vnalpha eval research-answers --ci
```

## CI behavior

The eval command should fail on:

```text
unsupported metric hallucination
missing caveat
missing artifact reference
execution-style language
missing refusal for unsafe prompt
```
