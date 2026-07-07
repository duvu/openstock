# Design: Phase 5.8 Research Workspace Command Layer

## Context

Phase 5 gives `vnalpha` a deterministic research pipeline and TUI. Phase 5.8 adds a command layer on top of the existing warehouse, scoring, watchlist, lineage, and data-quality surfaces.

The key design decision is to introduce a typed command/tool abstraction before adding natural language in Phase 5.9.

```text
User command
→ CommandParser
→ CommandRegistry
→ CommandHandler
→ LocalToolRegistry
→ Tool implementation
→ CommandResult
→ Renderer
→ research_session + tool_trace
```

## Design principles

### Deterministic before intelligent

Phase 5.8 must not rely on an LLM. It creates the stable command/tool substrate that later AI planning can call.

### Commands are not tools

A command is a user-facing intent. A tool is a typed internal capability.

Example:

```text
/explain FPT
```

may call tools such as:

```text
watchlist.get_candidate
candidate_score.get_breakdown
quality.get_latest_status
lineage.get_symbol_lineage
```

### Trace everything

Every command invocation must create a `research_session` row. Every tool call made by that command must create a `tool_trace` row linked to the session.

### Research-only boundary

The command layer must not introduce order, account, portfolio, or recommendation semantics.

Allowed language:

```text
research candidate
watchlist
score
setup
risk flag
evidence
lineage
data quality
```

Forbidden product behavior:

```text
place order
broker execution
account management
portfolio management
autonomous trading
LLM-only signal
unrestricted SQL
unrestricted filesystem access
unmediated internet access
```

## Proposed module layout

```text
vnalpha/src/vnalpha/commands/
├── __init__.py
├── grammar.py
├── parser.py
├── registry.py
├── models.py
├── errors.py
├── handlers/
│   ├── scan.py
│   ├── filter.py
│   ├── compare.py
│   ├── explain.py
│   ├── quality.py
│   ├── lineage.py
│   ├── note.py
│   ├── help.py
│   └── history.py
└── renderers/
    ├── rich_renderer.py
    └── textual_renderer.py

vnalpha/src/vnalpha/tools/
├── __init__.py
├── registry.py
├── models.py
├── errors.py
├── watchlist.py
├── scoring.py
├── features.py
├── quality.py
├── lineage.py
└── notes.py
```

## Data model

### `research_session`

Records one user command invocation.

Suggested fields:

```text
session_id            VARCHAR PRIMARY KEY
started_at            TIMESTAMPTZ NOT NULL
finished_at           TIMESTAMPTZ
status                VARCHAR NOT NULL
surface               VARCHAR NOT NULL     # cli | tui
command_text          VARCHAR NOT NULL
command_name          VARCHAR
parsed_args_json      VARCHAR
result_summary_json   VARCHAR
error_json            VARCHAR
```

### `tool_trace`

Records every internal tool call made during a command session.

Suggested fields:

```text
tool_trace_id         VARCHAR PRIMARY KEY
session_id            VARCHAR NOT NULL
tool_name             VARCHAR NOT NULL
started_at            TIMESTAMPTZ NOT NULL
finished_at           TIMESTAMPTZ
status                VARCHAR NOT NULL
input_json            VARCHAR
output_summary_json   VARCHAR
error_json            VARCHAR
```

### `research_note`

Stores user notes created from command workflows.

Suggested fields:

```text
note_id               VARCHAR PRIMARY KEY
created_at            TIMESTAMPTZ NOT NULL
updated_at            TIMESTAMPTZ
symbol                VARCHAR
session_id            VARCHAR
note_text             VARCHAR NOT NULL
tags_json             VARCHAR
```

## Command grammar

Phase 5.8 should support a deliberately small grammar.

```text
COMMAND       := "/" NAME [ARGUMENTS]
NAME          := [a-z][a-z0-9_-]*
ARGUMENTS     := POSITIONAL* FILTER* OPTION*
POSITIONAL    := SYMBOL | UNIVERSE | TEXT
FILTER        := KEY OP VALUE
OPTION        := "--" KEY [VALUE]
OP            := "=" | "!=" | ">" | ">=" | "<" | "<=" | "contains"
```

Examples:

```text
/scan VN30
/filter score>=0.70 setup=ACCUMULATION_BASE
/compare FPT VNM MWG
/explain FPT
/quality FPT
/lineage FPT
/note FPT "watch RS and liquidity"
/help
/history --limit 20
```

## Command model

```python
class ParsedCommand:
    command_name: str
    raw_text: str
    positional: list[str]
    filters: list[CommandFilter]
    options: dict[str, str | bool]
```

```python
class CommandResult:
    status: Literal["SUCCESS", "FAILED", "VALIDATION_ERROR"]
    title: str
    summary: str | None
    tables: list[ResultTable]
    panels: list[ResultPanel]
    artifacts: list[ResultArtifact]
    warnings: list[str]
    error: CommandError | None
```

## Local tool model

```python
class ToolSpec:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    permission: ToolPermission
```

Initial permission set:

```text
READ_WATCHLIST
READ_FEATURES
READ_SCORE
READ_QUALITY
READ_LINEAGE
WRITE_NOTE
READ_HISTORY
```

Phase 5.8 must not include:

```text
NETWORK_ACCESS
PYTHON_EXECUTION
MCP_TOOL_CALL
CODEBASE_MUTATION
BROKER_EXECUTION
```

## Initial command behavior

### `/scan`

Reads the latest or specified watchlist/universe view and returns ranked candidates.

Examples:

```text
/scan
/scan VN30
/scan --date 2026-07-06
```

### `/filter`

Filters candidate scores or watchlist rows by deterministic conditions.

Examples:

```text
/filter score>=0.70
/filter class=STRONG_CANDIDATE setup=ACCUMULATION_BASE
/filter risk_flags not_contains THIN_VOLUME
```

### `/compare`

Compares a small list of symbols using feature snapshot, score breakdown, setup type, risk flags, and data quality.

Example:

```text
/compare FPT VNM MWG
```

### `/explain`

Explains one symbol from persisted deterministic artifacts only.

Example:

```text
/explain FPT
```

The explanation must include:

```text
score
candidate_class
setup_type
score breakdown
evidence
risk flags
data quality status
lineage
```

### `/quality`

Shows data-quality state for a symbol or for the latest watchlist.

Examples:

```text
/quality
/quality FPT
```

### `/lineage`

Shows source provider, ingestion run, selected canonical row source, feature date, and scoring version.

Example:

```text
/lineage FPT
```

### `/note`

Creates a user note linked to a symbol and research session.

Example:

```text
/note FPT "watch whether relative strength persists"
```

### `/help`

Lists available commands and usage.

### `/history`

Shows recent command sessions and their statuses.

## CLI integration

Add a command runner surface:

```bash
vnalpha cmd "/scan VN30"
vnalpha cmd "/explain FPT"
vnalpha cmd "/history --limit 20"
```

The CLI runner must:

```text
parse command
open warehouse connection
create research_session
execute handler
record tool_trace
render result via Rich
finish research_session
return non-zero exit code on validation/runtime errors
```

## TUI integration

Add a command input bar and result panel.

Required behavior:

```text
- input bar accepts slash commands.
- command result renders as table/panel output.
- failed command shows validation error without crashing TUI.
- command history is available in the TUI.
- watchlist/detail screens can open command-derived views.
```

## Error handling

Errors should be typed and user-facing messages should be concise.

Suggested errors:

```text
UnknownCommandError
CommandParseError
CommandValidationError
ToolPermissionError
ToolExecutionError
RendererError
```

All failed command sessions must be persisted with status `FAILED` or `VALIDATION_ERROR`.

## Testing strategy

### Unit tests

```text
parser grammar
unknown command rejection
command registry lookup
filter expression parsing
symbol normalization
command result serialization
permission checks
```

### Integration tests

```text
/scan reads fixture watchlist
/filter filters fixture candidate scores
/compare returns multi-symbol table
/explain returns score/evidence/risk/lineage
/quality returns data-quality status
/lineage returns provider/ingestion/scoring lineage
/note persists note
/history returns session history
```

### TUI tests

```text
command input widget mounts
command result panel renders
invalid command displays error
command does not crash app
```

## Migration strategy

Add new tables through the existing DuckDB migration path:

```text
research_session
tool_trace
research_note
```

The tables are additive and do not change existing Phase 5 data structures.

## Compatibility

Existing commands must keep working:

```text
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv
vnalpha sync index
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
vnalpha tui
```

Phase 5.8 adds `vnalpha cmd` and TUI command input without breaking Phase 5.
