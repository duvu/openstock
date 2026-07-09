# Design: TUI Research Workflow Polish

## Architecture

```text
ComposerInput
  -> TuiInputRouter
  -> Command/Assistant result
  -> ResearchArtifactRenderer
  -> OutputStream
  -> optional responsive read-only side panels
```

## Proposed modules

```text
vnalpha/tui/renderers/research_artifact.py
vnalpha/tui/renderers/deep_analysis.py
vnalpha/tui/renderers/shortlist.py
vnalpha/tui/renderers/scenario.py
vnalpha/tui/renderers/evidence.py
vnalpha/tui/research_navigation.py
```

## Rendering principles

- Keep one primary OutputStream.
- Use semantic blocks for analysis, levels, caveats, evidence, scenarios, and artifacts.
- Optional panels must be read-only and responsive.
- Composer remains the only input widget.
- All long workflows should show status/progress and correlation ID.

## Workflows

### Deep analysis

Render:

```text
header
quality/freshness
trend/momentum/RS/volume/volatility blocks
levels
setup quality
caveats
artifact refs
```

### Shortlist

Render compact ranked table plus expandable rationale blocks.

### Scenario plan

Render scenario tree and checklist with policy-safe wording.

### Evidence

Render sample size, distribution table, regime split, and caveats.

## Keyboard actions

Allowed navigation actions:

```text
open artifact detail
back
copy artifact id
save note from artifact
route artifact to assistant
```

Disallowed actions:

```text
trade
order
connect broker
allocate
rebalance
```
