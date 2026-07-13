# Proposal: Research automation for opencode-like auto research

## Summary

Add OpenSpec for Phase C of the production/MVP2 OpenStock roadmap:

```text
Phase C: Research Automation
```

This phase turns the sandbox compute MVP into a practical auto research system for Vietnamese equity analysis.

It adds structured workflows for:

```text
indicator experiments
pattern scans
feature engineering
hypothesis tests
offline research metrics
```

The system remains inside the read-only research boundary.

## Why

Once sandbox compute exists, the next step is not arbitrary code execution. The next step is domain-shaped research automation.

OpenStock should let the user ask questions like:

```text
- Test whether 20-session relative strength predicts breakout candidates.
- Create a volume dry-up indicator and validate it on historical data.
- Scan for accumulation base patterns with volatility contraction.
- Compare feature distributions between strong and weak candidates.
- Run an offline event study for a setup definition.
```

The system should translate those requests into reproducible research jobs, not trading actions.

## Goals

- Add first-class research automation concepts: experiment, feature, hypothesis, pattern scan, offline event study.
- Add command surface for `/experiment`, `/feature`, `/hypothesis`, and `/pattern` or equivalent.
- Reuse sandbox compute for generated calculations.
- Persist every research output as a reproducible artifact.
- Keep generated code and dataset references attached to every result.
- Add validation and quality checks for research outputs.
- Support assistant-generated plans for research automation.
- Preserve read-only research boundary.

## Non-goals

- No live trading.
- No broker/order/account/portfolio/margin/transfer/allocation integration.
- No trading execution strategy deployment.
- No personalized financial advice engine.
- No automated buy/sell recommendations.
- No claims that research metrics predict future returns with certainty.

## Scope

### Research automation objects

The implementation SHALL define or model these concepts:

```text
ResearchExperiment
ResearchFeature
ResearchHypothesis
PatternScan
OfflineEventStudy
ResearchArtifact
```

Each object SHALL include:

```text
id
name/purpose
input dataset references
definition or generated code reference
parameters
result artifact references
quality status
lineage
correlation_id
created_at
```

### Command surface

The composer SHALL support at minimum:

```text
/experiment indicator <description>
/experiment backtest <event-study-description>
/feature create <definition>
/feature validate <feature-id-or-name>
/hypothesis test <hypothesis-text>
/pattern scan <pattern-description>
```

The term `backtest` in this system SHALL mean offline research event study. It SHALL NOT imply live execution, broker routing, or portfolio action.

### Assistant integration

Natural-language requests SHALL route to research automation plans when they require experimental computation.

Example plan:

```text
1. Resolve dataset snapshot.
2. Define feature or pattern calculation.
3. Create SandboxJob.
4. Execute approved sandbox job.
5. Validate output schema.
6. Persist artifact.
7. Synthesize finding with caveats.
```

### Output expectations

Research automation output SHALL include:

```text
summary.md
result.json
metrics table
sample size
period coverage
data quality caveats
lineage
optional charts
reproducibility manifest
```

### Research caveats

The assistant SHALL present research conclusions as evidence, not recommendations.

It SHALL include caveats such as:

```text
sample size
period coverage
survivorship bias risk
data quality issues
lookahead bias risk
transaction cost exclusion if applicable
```

## Success criteria

This phase is complete only when:

```text
- `/experiment indicator` creates a reproducible indicator experiment.
- `/experiment backtest` runs an offline event study and labels it as research-only.
- `/feature create` persists a feature definition and artifact reference.
- `/feature validate` validates feature output against expected schema.
- `/hypothesis test` creates a structured hypothesis test artifact.
- `/pattern scan` scans historical data for a pattern definition.
- All workflows run through sandbox or approved deterministic research tools.
- Every result includes lineage, quality, sample coverage, and caveats.
- No workflow introduces broker/order/account/portfolio/margin/trading execution.
```

## Validation commands

Run:

```bash
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
pytest vnalpha/tests -k "experiment or feature or hypothesis or pattern"
```

## Production boundary

This phase creates an auto research workspace, not an auto trading system.

All research automation must remain inside the read-only research boundary and must produce evidence artifacts, not trading actions.
