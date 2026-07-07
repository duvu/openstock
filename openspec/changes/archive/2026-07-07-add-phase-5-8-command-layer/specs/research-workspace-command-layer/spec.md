# Specification: Research Workspace Command Layer

## ADDED Requirements

### Requirement: Command layer shall parse deterministic slash commands

`vnalpha` SHALL provide a deterministic parser for slash commands.

The parser SHALL support:

```text
/scan
/filter
/compare
/explain
/quality
/lineage
/note
/help
/history
```

The parser SHALL return a structured `ParsedCommand` containing:

```text
command_name
raw_text
positional arguments
filters
options
```

The parser SHALL reject malformed commands without executing any tool.

#### Scenario: Parse a simple command

- **GIVEN** the user enters `/explain FPT`
- **WHEN** the command parser runs
- **THEN** it SHALL return command_name `explain`
- **AND** positional arguments SHALL contain `FPT`
- **AND** no tool SHALL execute during parsing

#### Scenario: Parse filters

- **GIVEN** the user enters `/filter score>=0.70 setup=ACCUMULATION_BASE`
- **WHEN** the command parser runs
- **THEN** it SHALL return command_name `filter`
- **AND** filters SHALL include `score >= 0.70`
- **AND** filters SHALL include `setup = ACCUMULATION_BASE`

#### Scenario: Reject malformed syntax

- **GIVEN** the user enters `/filter score>>0.70`
- **WHEN** the command parser runs
- **THEN** the command SHALL fail with `CommandParseError`
- **AND** no command handler SHALL execute
- **AND** no local tool SHALL execute

---

### Requirement: Command registry shall allow only registered commands

`vnalpha` SHALL provide a command registry that maps command names to typed handlers.

The registry SHALL:

```text
- register command metadata
- reject duplicate command names
- reject unknown commands
- expose command usage and examples for /help
```

#### Scenario: Resolve a registered command

- **GIVEN** `/scan` is registered
- **WHEN** the user enters `/scan VN30`
- **THEN** the registry SHALL resolve the `scan` handler

#### Scenario: Reject an unknown command

- **GIVEN** `/trade` is not registered
- **WHEN** the user enters `/trade FPT`
- **THEN** the registry SHALL return `UnknownCommandError`
- **AND** no tool SHALL execute

---

### Requirement: Local tool registry shall expose typed research tools only

`vnalpha` SHALL provide a local tool registry for deterministic research operations.

The local tool registry SHALL expose initial tools:

```text
watchlist.scan
watchlist.filter
candidate.compare
candidate.explain
quality.get_status
lineage.get_symbol_lineage
note.create
history.list_sessions
```

Each tool SHALL define:

```text
name
description
input schema
output schema
permission
```

Phase 5.8 tools SHALL NOT include network access, Python execution, MCP calls, codebase mutation, broker execution, account management, or portfolio management.

#### Scenario: Execute an allowed tool

- **GIVEN** the command `/explain FPT`
- **WHEN** the handler executes
- **THEN** it MAY call `candidate.explain`
- **AND** it MAY call `quality.get_status`
- **AND** it MAY call `lineage.get_symbol_lineage`
- **BUT** it SHALL NOT call any network, Python, MCP, code mutation, or broker tool

#### Scenario: Block a disallowed permission

- **GIVEN** a handler tries to call a tool with permission `NETWORK_ACCESS`
- **WHEN** Phase 5.8 permission checks run
- **THEN** the call SHALL fail with `ToolPermissionError`
- **AND** the session SHALL be marked failed

---

### Requirement: Command execution shall persist research sessions

Every command invocation SHALL create a `research_session` record.

The session record SHALL include:

```text
session_id
started_at
finished_at
status
surface
command_text
command_name
parsed_args_json
result_summary_json
error_json
```

Valid status values SHALL include:

```text
RUNNING
SUCCESS
FAILED
VALIDATION_ERROR
```

#### Scenario: Successful command session

- **GIVEN** the user enters `/scan`
- **WHEN** the command completes successfully
- **THEN** a `research_session` row SHALL exist
- **AND** its status SHALL be `SUCCESS`
- **AND** it SHALL include the raw command text
- **AND** it SHALL include parsed argument metadata

#### Scenario: Failed command session

- **GIVEN** the user enters `/unknown`
- **WHEN** the command fails validation
- **THEN** a `research_session` row SHALL exist
- **AND** its status SHALL be `VALIDATION_ERROR`
- **AND** it SHALL include error metadata

---

### Requirement: Tool calls shall be traced

Every tool call made during command execution SHALL create a `tool_trace` record linked to the command session.

The trace record SHALL include:

```text
tool_trace_id
session_id
tool_name
started_at
finished_at
status
input_json
output_summary_json
error_json
```

#### Scenario: Trace tool calls for explain command

- **GIVEN** the user enters `/explain FPT`
- **WHEN** the command handler calls local tools
- **THEN** each local tool call SHALL create a `tool_trace` row
- **AND** each row SHALL reference the parent `research_session`
- **AND** each row SHALL include input and output summary metadata

#### Scenario: Trace failed tool call

- **GIVEN** a command handler calls a local tool with invalid input
- **WHEN** the tool fails
- **THEN** a `tool_trace` row SHALL be persisted with status `FAILED`
- **AND** error metadata SHALL be stored

---

### Requirement: Command results shall render consistently

Command handlers SHALL return a structured `CommandResult`.

`CommandResult` SHALL support:

```text
status
title
summary
tables
panels
artifacts
warnings
error
```

CLI and TUI renderers SHALL consume the same `CommandResult` model.

#### Scenario: Render scan result in CLI

- **GIVEN** `/scan` returns candidate rows
- **WHEN** the CLI renderer receives the result
- **THEN** it SHALL render a table containing rank, symbol, score, candidate class, setup type, and risk flags

#### Scenario: Render explain result in TUI

- **GIVEN** `/explain FPT` returns score breakdown and evidence
- **WHEN** the TUI renderer receives the result
- **THEN** it SHALL show score, class, setup, evidence, risk flags, data quality, and lineage panels

---

### Requirement: CLI shall expose a command runner

`vnalpha` SHALL expose a CLI command runner:

```bash
vnalpha cmd "<slash-command>"
```

The CLI runner SHALL:

```text
- parse the slash command
- create a research_session
- execute the registered handler
- trace all local tool calls
- render the CommandResult with Rich
- exit non-zero on parse, validation, permission, or runtime errors
```

#### Scenario: Run help command

- **GIVEN** the user runs `vnalpha cmd "/help"`
- **WHEN** the command completes
- **THEN** the output SHALL list registered Phase 5.8 commands and usage examples

#### Scenario: Run scan command

- **GIVEN** the warehouse contains a daily watchlist
- **WHEN** the user runs `vnalpha cmd "/scan"`
- **THEN** the output SHALL show research candidates from the watchlist
- **AND** the command SHALL be persisted in `research_session`

---

### Requirement: TUI shall expose command input and result surfaces

The TUI SHALL provide a command input surface for slash commands.

The TUI SHALL provide a command result surface that can render tables, panels, warnings, and validation errors.

#### Scenario: Execute command from TUI

- **GIVEN** the TUI is open
- **WHEN** the user enters `/quality FPT`
- **THEN** the TUI SHALL execute the command
- **AND** display a data-quality result panel
- **AND** persist the command session with surface `tui`

#### Scenario: Invalid command does not crash TUI

- **GIVEN** the TUI is open
- **WHEN** the user enters `/unknown`
- **THEN** the TUI SHALL display a validation error
- **AND** the TUI SHALL remain usable
- **AND** the failed command session SHALL be persisted

---

### Requirement: Scan command shall return research candidates

`/scan` SHALL return the daily watchlist or a filtered universe view.

It SHALL include:

```text
rank
symbol
score
candidate_class
setup_type
risk_flags
data_quality_status
```

#### Scenario: Scan latest watchlist

- **GIVEN** a daily watchlist exists for the target date
- **WHEN** the user enters `/scan`
- **THEN** the command SHALL return ranked research candidates

#### Scenario: Scan named universe

- **GIVEN** VN30 can be resolved
- **WHEN** the user enters `/scan VN30`
- **THEN** the command SHALL scan VN30 candidates using persisted deterministic artifacts

---

### Requirement: Filter command shall apply safe deterministic filters

`/filter` SHALL apply safe filter expressions to candidate score or watchlist rows.

Allowed filter fields SHALL include:

```text
symbol
score
candidate_class
setup_type
risk_flags
data_quality_status
```

The filter engine SHALL NOT execute raw SQL from user input.

#### Scenario: Filter by score and setup

- **GIVEN** candidate scores exist for the target date
- **WHEN** the user enters `/filter score>=0.70 setup=ACCUMULATION_BASE`
- **THEN** the command SHALL return only rows matching both filters

#### Scenario: Reject unsafe filter field

- **GIVEN** the user enters `/filter raw_sql="drop table candidate_score"`
- **WHEN** the filter parser runs
- **THEN** the command SHALL fail validation
- **AND** no SQL derived directly from the user input SHALL execute

---

### Requirement: Compare command shall compare deterministic symbol artifacts

`/compare` SHALL compare a small list of symbols using persisted deterministic artifacts.

The result SHALL include:

```text
symbol
score
candidate_class
setup_type
score breakdown
risk flags
data quality
relative strength fields when available
```

#### Scenario: Compare three symbols

- **GIVEN** candidate scores and feature snapshots exist for FPT, VNM, and MWG
- **WHEN** the user enters `/compare FPT VNM MWG`
- **THEN** the command SHALL return a comparison table

---

### Requirement: Explain command shall explain one candidate from persisted artifacts

`/explain SYMBOL` SHALL explain a symbol using stored candidate score, evidence, risk flags, lineage, and data-quality state.

It SHALL NOT create an LLM-only explanation or override deterministic scores.

#### Scenario: Explain candidate

- **GIVEN** candidate score exists for FPT
- **WHEN** the user enters `/explain FPT`
- **THEN** the command SHALL return score, candidate class, setup type, score breakdown, evidence, risk flags, data quality, and lineage

#### Scenario: Missing candidate score

- **GIVEN** candidate score does not exist for XYZ
- **WHEN** the user enters `/explain XYZ`
- **THEN** the command SHALL return a validation or not-found result
- **AND** it SHALL suggest running the Phase 5 scoring pipeline first

---

### Requirement: Quality command shall show data-quality state

`/quality` SHALL show quality status for a symbol or for the active watchlist.

#### Scenario: Symbol quality

- **GIVEN** canonical OHLCV exists for FPT
- **WHEN** the user enters `/quality FPT`
- **THEN** the command SHALL show latest canonical quality status and any rejected-symbol records

#### Scenario: Watchlist quality

- **GIVEN** the daily watchlist exists
- **WHEN** the user enters `/quality`
- **THEN** the command SHALL show data-quality state for watchlist members

---

### Requirement: Lineage command shall show source lineage

`/lineage SYMBOL` SHALL show lineage for a symbol.

The result SHALL include available:

```text
selected provider
ingestion_run_id
source endpoint
feature date
scoring version
generated_at
```

#### Scenario: Show symbol lineage

- **GIVEN** FPT has canonical data and a candidate score
- **WHEN** the user enters `/lineage FPT`
- **THEN** the command SHALL show provider, ingestion, feature, and scoring lineage

---

### Requirement: Note command shall persist research notes

`/note` SHALL create a user note linked to a symbol and command session.

#### Scenario: Create symbol note

- **GIVEN** the user enters `/note FPT "watch relative strength"`
- **WHEN** the command completes
- **THEN** a `research_note` row SHALL be created
- **AND** it SHALL reference symbol `FPT`
- **AND** it SHALL reference the parent session

---

### Requirement: History command shall show research sessions

`/history` SHALL show recent research sessions.

#### Scenario: List recent sessions

- **GIVEN** research_session rows exist
- **WHEN** the user enters `/history --limit 20`
- **THEN** the command SHALL return up to 20 recent sessions
- **AND** include command text, status, surface, started_at, and finished_at

---

### Requirement: Command layer shall preserve research-only safety boundaries

Phase 5.8 SHALL remain a research-only command layer.

It SHALL NOT:

```text
- place orders
- connect to broker execution APIs
- manage accounts
- manage portfolios
- provide buy/sell instructions
- execute generated Python
- access the internet
- call MCP tools
- mutate source code
- execute unrestricted SQL
```

#### Scenario: Trading-like command is rejected

- **GIVEN** the user enters `/order FPT`
- **WHEN** the command registry resolves the command
- **THEN** it SHALL reject the command as unknown or forbidden
- **AND** no tool SHALL execute

#### Scenario: Research wording is enforced

- **GIVEN** a command result is rendered
- **WHEN** the result text is generated
- **THEN** it SHALL use research terms such as `watchlist`, `candidate`, `evidence`, and `risk flag`
- **AND** it SHALL NOT use execution terms such as `buy order`, `sell order`, or `portfolio action`
