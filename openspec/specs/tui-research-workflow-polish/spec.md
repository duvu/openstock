# tui-research-workflow-polish Specification

## Purpose
TBD - created by archiving change tui-research-workflow-polish. Update Purpose after archive.
## Requirements
### Requirement: Composer-first research workflow

The TUI SHALL remain composer-first while supporting richer research outputs.

#### Scenario: Research features are added

- **WHEN** deep analysis, shortlist, scenario, or evidence output is rendered
- **THEN** the default TUI still has one primary ComposerInput and one primary OutputStream

### Requirement: Research artifact rendering

The TUI SHALL render structured research artifacts clearly.

#### Scenario: Deep analysis output is returned

- **WHEN** `/analyze FPT` returns an artifact
- **THEN** the TUI renders semantic blocks for quality, trend, momentum, relative strength, volume, volatility, levels, setup quality, caveats, and artifact references

### Requirement: Read-only optional panels

Optional panels SHALL be read-only and responsive.

#### Scenario: Terminal is narrow

- **WHEN** terminal width is below the configured breakpoint
- **THEN** optional panels collapse and OutputStream remains usable

### Requirement: No execution controls

The TUI SHALL not expose trading execution controls.

#### Scenario: Keyboard actions are configured

- **WHEN** research workflow keybindings are available
- **THEN** they support navigation, note saving, and assistant routing only, not trade/order/broker/account actions

### Requirement: Long workflow status

The TUI SHALL show status for long-running research workflows.

#### Scenario: Scenario plan generation is running

- **WHEN** a long research workflow is active
- **THEN** status output includes progress state and correlation or artifact ID

