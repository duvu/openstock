# Phase 5.8 Research Workspace Command Layer

The command layer adds structured slash-command access to the vnalpha research pipeline. It provides a deterministic, traceable interface between the user and the warehouse — without an LLM, without network calls, and without broker semantics.

## Architecture

```
User command text
  → CommandParser        parse slash-command grammar
  → CommandRegistry      look up handler by command name
  → CommandHandler       orchestrate tool calls
  → LocalToolRegistry    call typed, permission-checked tools
  → Tool implementation  read from warehouse / write notes
  → CommandResult        structured result (tables, panels, artifacts)
  → Renderer             Rich (CLI) or markup (TUI)
  → research_session + tool_trace   (persisted audit trail)
```

Every command invocation creates a `research_session` row. Every tool call within that session creates a `tool_trace` row.

## Command Grammar

```
COMMAND    := "/" NAME [ARGUMENTS]
NAME       := [a-z][a-z0-9_-]*
ARGUMENTS  := POSITIONAL* FILTER* OPTION*
POSITIONAL := SYMBOL | UNIVERSE | QUOTED_TEXT
FILTER     := KEY OP VALUE
OPTION     := "--" KEY [VALUE]
OP         := "=" | "!=" | ">" | ">=" | "<" | "<=" | "contains"
```

Symbols are normalised to uppercase. Candidate classes and setup types are normalised to canonical forms. Dates accept ISO format (`2026-07-01`) or the special value `today`.

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/scan` | Return ranked research candidates from watchlist | `/scan VN30 --date today` |
| `/analyze` | Deep persisted research analysis for one symbol | `/analyze FPT --date today` |
| `/watchlist-summary` | Structural watchlist synthesis with groups and caveats | `/watchlist-summary --top 20` |
| `/shortlist` | Deterministic research shortlist from persisted watchlist evidence | `/shortlist --limit 8` |
| `/research-plan` | Conditional research-only scenario planning | `/research-plan FPT` |
| `/setup-evidence` | Historical evidence for a setup type or symbol | `/setup-evidence ACCUMULATION_BASE --horizon 20` |
| `/filter` | Filter candidates by deterministic conditions | `/filter score>=0.70 setup=ACCUMULATION_BASE` |
| `/compare` | Side-by-side comparison of symbols | `/compare FPT VNM MWG` |
| `/explain` | Full evidence breakdown for one symbol | `/explain FPT --date 2026-07-01` |
| `/quality` | Data quality status (symbol or watchlist) | `/quality FPT` |
| `/lineage` | Ingestion and scoring lineage for a symbol | `/lineage FPT` |
| `/note` | Persist a research note | `/note FPT "watch RS and volume"` |
| `/history` | List recent research sessions | `/history --limit 20` |
| `/help` | List all registered commands | `/help` |

### `/scan`

Returns ranked candidates from the latest (or specified) watchlist. Results include symbol, candidate class, score, setup type, and active risk flags.

```bash
vnalpha cmd "/scan"
vnalpha cmd "/scan VN30"
vnalpha cmd "/scan --date 2026-07-01"
```

### `/filter`

Filters candidate scores or watchlist rows using safe deterministic expressions. Supported filter keys: `score`, `class` (→ `candidate_class`), `setup` (→ `setup_type`), `symbol`.

```bash
vnalpha cmd "/filter score>=0.70"
vnalpha cmd "/filter class=STRONG_CANDIDATE setup=ACCUMULATION_BASE"
vnalpha cmd "/filter score>0.60 --date 2026-07-01"
```

### `/compare`

Compares two or more symbols. Shows score breakdown, setup type, risk flags, and data quality side by side.

```bash
vnalpha cmd "/compare FPT VNM"
vnalpha cmd "/compare FPT VNM MWG --date 2026-07-01"
```

### `/analyze`

Deep persisted research analysis for one symbol. Output favors semantic blocks over raw rows: quality and freshness, trend and momentum, relative strength and volume, volatility and levels, setup quality, and scenario summary.

```bash
vnalpha cmd "/analyze FPT"
vnalpha cmd "/analyze FPT --date 2026-07-01"
```

### `/watchlist-summary`

Aggregates the persisted watchlist into candidate-class, setup, sector, quality, and risk distributions plus top candidates.

```bash
vnalpha cmd "/watchlist-summary"
vnalpha cmd "/watchlist-summary --top 20"
```

### `/shortlist`

Builds a deterministic research shortlist with caveated risk flags and methodological disclosure.

```bash
vnalpha cmd "/shortlist"
vnalpha cmd "/shortlist --setup MOMENTUM_CONTINUATION --limit 8"
```

### `/research-plan`

Builds a conditional, research-only scenario plan for one symbol using persisted deep-analysis context.

```bash
vnalpha cmd "/research-plan FPT"
vnalpha cmd "/research-plan FPT --date 2026-07-01"
```

### `/setup-evidence`

Returns persisted historical setup evidence by setup type. When given a symbol, the command resolves the latest persisted setup type first.

```bash
vnalpha cmd "/setup-evidence ACCUMULATION_BASE --horizon 20"
vnalpha cmd "/setup-evidence FPT --date 2026-07-01"
```

### `/explain`

Full evidence breakdown for one symbol using persisted `candidate_score` data. Output includes:
- Score summary (composite score, candidate class, setup type)
- Score breakdown (trend, RS, volume, base, breakout, risk quality sub-scores)
- Risk flags
- Lineage (scoring version, feature date, generated timestamp)

```bash
vnalpha cmd "/explain FPT"
vnalpha cmd "/explain FPT --date 2026-07-01"
```

### `/quality`

Data quality status for a symbol or the full watchlist.

```bash
vnalpha cmd "/quality FPT"
vnalpha cmd "/quality"           # watchlist-level overview
```

### `/lineage`

Shows the full data lineage trail: provider, ingestion run, feature snapshot date, scoring version, and generated-at timestamp.

```bash
vnalpha cmd "/lineage FPT"
```

### `/note`

Persists a research note attached to a symbol and optionally tagged. Notes are stored in `research_note` and linked to the current session.

```bash
vnalpha cmd "/note FPT \"watching RS divergence\""
vnalpha cmd "/note FPT \"compressed base\" --tags base,volume"
```

### `/history`

Lists recent research sessions with their command text, status, and timestamp.

```bash
vnalpha cmd "/history"
vnalpha cmd "/history --limit 5"
```

## CLI Usage

```bash
# Run a command
vnalpha cmd "/scan VN30"
vnalpha cmd "/explain FPT"
vnalpha cmd "/help"

# Errors produce non-zero exit codes
vnalpha cmd "/unknown_command"   # exit 1 (UnknownCommandError)
vnalpha cmd "/explain"           # exit 1 (missing required symbol)
```

## TUI Usage

Press `c` in the TUI to open the command screen. Type any slash command in the input bar. The result is rendered in the panel below.

## Warehouse Tables

### `research_session`

One row per command invocation.

| Column | Type | Description |
|--------|------|-------------|
| `session_id` | VARCHAR PK | UUID |
| `started_at` | TIMESTAMPTZ | Invocation timestamp |
| `finished_at` | TIMESTAMPTZ | Completion timestamp |
| `status` | VARCHAR | `SUCCESS` / `FAILED` |
| `surface` | VARCHAR | `cli` / `tui` |
| `command_text` | VARCHAR | Original user input |
| `command_name` | VARCHAR | Parsed command name |
| `parsed_args_json` | VARCHAR | JSON positional + filters + options |
| `result_summary_json` | VARCHAR | JSON result summary |
| `error_json` | VARCHAR | JSON error if failed |

### `tool_trace`

One row per tool call within a session.

| Column | Type | Description |
|--------|------|-------------|
| `tool_trace_id` | VARCHAR PK | UUID |
| `session_id` | VARCHAR | FK to `research_session` |
| `tool_name` | VARCHAR | e.g. `watchlist.scan` |
| `started_at` | TIMESTAMPTZ | Call start |
| `finished_at` | TIMESTAMPTZ | Call end |
| `status` | VARCHAR | `SUCCESS` / `FAILED` |
| `input_json` | VARCHAR | JSON input to tool |
| `output_summary_json` | VARCHAR | JSON output summary |
| `error_json` | VARCHAR | JSON error if failed |

### `research_note`

User notes created via `/note`.

| Column | Type | Description |
|--------|------|-------------|
| `note_id` | VARCHAR PK | UUID |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update |
| `symbol` | VARCHAR | Attached symbol |
| `session_id` | VARCHAR | Session that created this note |
| `note_text` | VARCHAR | Note content |
| `tags_json` | VARCHAR | JSON list of tags |

## Tool Permissions

The tool layer uses an explicit permission model. All Phase 5.8 tools operate within the read/write-note boundary.

**Allowed:**
- `READ_WATCHLIST` — read daily_watchlist and candidate_score
- `READ_FEATURES` — read feature_snapshot
- `READ_SCORE` — read candidate_score evidence and lineage
- `READ_QUALITY` — read canonical_ohlcv quality_status
- `READ_LINEAGE` — read ingestion_run and scoring lineage
- `WRITE_NOTE` — insert research_note rows
- `READ_HISTORY` — read research_session and tool_trace

**Forbidden (blocked at registration and test time):**
- `NETWORK_ACCESS`
- `PYTHON_EXECUTION`
- `MCP_TOOL_CALL`
- `CODEBASE_MUTATION`
- `BROKER_EXECUTION`

## Research-Only Boundary

The command layer enforces the same research-only constraint as the rest of vnalpha. Forbidden language and behavior:

- No buy / sell / order / portfolio / account / broker / trade terms in command outputs
- No autonomous recommendations
- No network calls from handlers or tools
- No SQL beyond the approved repository functions
- No filesystem access outside the configured warehouse path

## Phase 5.9 Handoff

Phase 5.8 is intentionally LLM-free. It creates the stable typed substrate that Phase 5.9 will use:

1. **Command grammar is defined** — a natural-language planner can emit validated `/scan`, `/explain`, etc. calls
2. **Tool specs have typed schemas** — input/output schemas allow LLM planning with validation
3. **Session and trace tables exist** — audit trail is ready for AI session management
4. **Permission model is in place** — Phase 5.9 will not be able to add forbidden permissions without test failures

Phase 5.9 integration point: accept natural language, translate to one or more `ParsedCommand` objects via an LLM planner, execute through the existing `CommandRegistry`, and return `CommandResult` objects for rendering. No Phase 5.8 code needs to change.
