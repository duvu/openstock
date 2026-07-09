# Design: Research Automation for OpenStock Auto Research

## Status

OpenSpec-only design for Phase C.

This change depends on:

```text
Phase A: production control plane
Phase B: sandboxed compute MVP
```

Research automation SHOULD NOT be implemented before the control plane and sandbox runner are production-safe.

## Target capability

Research automation turns OpenStock from a command-driven research shell into an opencode-like auto research workspace.

The system should let users ask for structured research workflows such as:

```text
/experiment indicator relative strength 20 sessions vs VNINDEX
/feature create rs_20 = stock_return_20d - vnindex_return_20d
/feature validate rs_20
/hypothesis test symbols with rs_20 > 0 have better 10-session forward return
/pattern scan accumulation base with volatility contraction and volume dry-up
/experiment backtest breakout event after accumulation base, horizon 10 sessions
```

The output is evidence, not trading advice.

## Non-negotiable boundary

Research automation SHALL remain inside the no-trading-execution boundary:

```text
no broker integration
no order placement
no account access
no live portfolio action
no margin
no transfer
no allocation/rebalance execution
no live automated trading
```

Backtest-like workflows SHALL be called offline research event studies in user-facing output unless the command name must remain `/experiment backtest` for convenience.

## Architecture

```text
ComposerInput / Chat
  -> TuiInputRouter
  -> ResearchAutomationRouter
  -> ResearchAutomationPlanner
  -> DatasetResolver
  -> SandboxJobBuilder
  -> SandboxRunner
  -> OutputValidator
  -> ResearchArtifactWriter
  -> AnswerSynthesizer / OutputStream
  -> Audit + Trace + Commands + Errors
```

## Proposed modules

```text
vnalpha/research_automation/
  __init__.py
  models.py
  router.py
  planner.py
  dataset_resolver.py
  artifact_writer.py
  validators.py
  caveats.py
  lineage.py
  commands.py

vnalpha/commands/handlers/experiment.py
vnalpha/commands/handlers/feature.py
vnalpha/commands/handlers/hypothesis.py
vnalpha/commands/handlers/pattern.py
```

Optional after MVP:

```text
vnalpha/research_automation/templates/
  indicator_relative_strength.py.j2
  feature_expression.py.j2
  hypothesis_event_study.py.j2
  pattern_accumulation_base.py.j2
```

## Data contracts

### ResearchArtifact

```text
artifact_id: str
artifact_type: indicator_experiment | feature | hypothesis_test | pattern_scan | offline_event_study
name: str
purpose: str
created_at: datetime
created_by: tui | cli | assistant
correlation_id: str
status: created | running | succeeded | failed | rejected | validated | promoted
input_datasets: list[DatasetRef]
sandbox_job_id: str | null
parameters: dict
metrics: dict
lineage: dict
quality_status: dict
caveats: list[str]
outputs: ArtifactOutputs
```

### DatasetRef

```text
dataset_name: str
snapshot_id: str | null
symbols: list[str]
start_date: str | null
end_date: str | null
interval: str
row_count: int | null
quality_status: dict
```

### ArtifactOutputs

```text
summary_md: path
result_json: path
manifest_json: path
metrics_table: path | null
candidate_table: path | null
chart_paths: list[path]
generated_code_path: path | null
```

## Artifact layout

Research automation artifacts SHOULD be stored under the same run/correlation tree as sandbox outputs:

```text
logs/runs/<run-id>/research/<artifact-id>/
  manifest.json
  result.json
  summary.md
  generated_code.py
  metrics.csv
  candidates.csv
  charts/
  lineage.json
  validation.json
```

If warehouse-backed persistence is used, database rows SHOULD contain metadata and file paths rather than duplicating large artifacts.

## Command contracts

### /experiment indicator

```text
/experiment indicator <description> [--universe UNIVERSE] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

Expected result:

```text
ResearchArtifact(type=indicator_experiment)
summary.md
result.json
metrics.csv
lineage.json
validation.json
```

### /experiment backtest

```text
/experiment backtest <offline-event-study-description> [--horizon N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

This MUST be rendered as an offline research event study.

Expected caveats:

```text
not investment advice
not live trading
transaction cost caveat
lookahead bias caveat
survivorship bias caveat
sample-size caveat
```

### /feature create

```text
/feature create <feature-expression-or-description>
```

Example:

```text
/feature create rs_20 = stock_return_20d - vnindex_return_20d
```

The system SHOULD persist feature definition before computing full output.

### /feature validate

```text
/feature validate <feature-id-or-name>
```

Validation checks:

```text
schema valid
symbol coverage valid
date coverage valid
missing ratio within threshold
lineage present
quality status present
no lookahead fields
```

### /hypothesis test

```text
/hypothesis test <hypothesis-text>
```

Planner SHOULD parse:

```text
sample universe
condition
outcome variable
holding horizon
metric
period
```

If parsing is ambiguous, produce a plan that states assumptions rather than silently choosing arbitrary defaults.

### /pattern scan

```text
/pattern scan <pattern-description> [--universe UNIVERSE] [--date YYYY-MM-DD]
```

MVP supported patterns:

```text
relative strength vs index
volume dry-up
volatility contraction
accumulation base
breakout confirmation
```

## Assistant planning rules

Natural-language requests SHOULD map into these deterministic intents:

```text
create_indicator_experiment
create_feature
validate_feature
test_hypothesis
scan_pattern
run_offline_event_study
```

Plan template:

```text
1. classify research automation intent
2. resolve dataset snapshot and universe
3. build deterministic research spec
4. create sandbox job if computation is required
5. require approval for generated code
6. execute sandbox job
7. validate outputs
8. persist research artifact
9. synthesize result with caveats
```

Generated code MUST be executed only through sandbox.

## Output quality requirements

Every research automation answer SHALL include:

```text
what was tested
universe and period
sample size
metrics
key caveats
data quality warnings
artifact id
reproducibility pointer
```

The answer SHALL NOT include personalized buy/sell recommendations.

## Validation strategy

Implementation PRs SHOULD add tests at these layers:

```text
unit: models, validators, caveats
unit: command parsers/handlers
unit: planner intent -> plan templates
integration: sandbox job -> artifact writer
integration: command -> artifact output
integration: assistant natural language -> approved sandbox job
policy: trading execution request refused
```

## Rollout strategy

Implement in slices:

```text
Slice 1: models + artifact layout + validators
Slice 2: /feature create + /feature validate
Slice 3: /experiment indicator
Slice 4: /pattern scan
Slice 5: /hypothesis test
Slice 6: /experiment backtest as offline event study
Slice 7: assistant natural-language integration
```

Do not implement all commands in one large PR.
