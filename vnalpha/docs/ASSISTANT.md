# Phase 5.9 Research Assistant

The Phase 5.9 research assistant adds natural-language query capability on top of the deterministic Phase 5.8 command layer. You ask research questions in plain English; the assistant classifies intent, builds a tool plan using only the Phase 5.8 allowlisted tools, executes them, and synthesizes a grounded answer.

## Overview

- **Phase**: 5.9
- **What it does**: Accepts a free-form research question, translates it to a structured tool plan, executes the plan against the local DuckDB warehouse, and returns a grounded answer with basis, risks/caveats, and missing-data disclosure.
- **When to use**: When you want to explore the watchlist, explain a candidate, compare symbols, or review data quality without memorising slash-command syntax.
- **What it is not**: Not a trading advisor, not a web search, not a code executor. All answers are grounded exclusively in persisted warehouse data.

---

## CLI Usage: `vnalpha ask`

```
vnalpha ask [OPTIONS] QUESTION
```

### Arguments

| Argument | Description |
|----------|-------------|
| `QUESTION` | Natural-language research question (required). Quote multi-word questions. |

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--date TEXT` | Target date (YYYY-MM-DD or `today`). Injected into the plan if not already present in the question. | Today's resolved date |
| `--show-plan` | Print the tool plan before the answer. | off |
| `--trace` | Print the tool trace summary after the answer. | off |
| `--no-execute` | Build and display the plan only; do not execute tools or call the LLM synthesizer. Useful for dry-runs. | off |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Answer returned successfully |
| `1` | Request refused, assistant error, or unexpected error |

### Examples

```bash
# Scan the watchlist for today
vnalpha ask "Show strongest VN30 candidates today"

# Explain a specific symbol
vnalpha ask "Why is FPT in the watchlist?"

# Compare three symbols
vnalpha ask "Compare FPT, VNM, and MWG"

# Data quality question
vnalpha ask "Which candidates have weak data quality?"

# Refusal example — trading execution is blocked
vnalpha ask "Buy FPT for me"
# → Exit code 1, panel: "Request Refused"

# Show plan without executing
vnalpha ask "Summarize today's watchlist" --no-execute

# Show plan and trace together
vnalpha ask "Explain HPG on 2026-06-30" --date 2026-06-30 --show-plan --trace
```

---

## Supported Intent Families

The assistant classifies every prompt into one of ten intents. Unrecognised or unsafe prompts map to `unsupported_or_unsafe` and are refused.

| Intent | Description | Example prompts |
|--------|-------------|-----------------|
| `scan_candidates` | Browse and rank watchlist candidates | "Show strongest VN30 candidates", "List top setups for today" |
| `filter_candidates` | Filter by score, class, setup, or risk flag | "Show candidates with score above 0.70", "Which setups are ACCUMULATION_BASE?" |
| `compare_symbols` | Side-by-side comparison of two or more symbols | "Compare FPT and VNM", "Compare FPT, VNM, MWG" |
| `explain_symbol` | Explain why a symbol is in the watchlist | "Why is FPT on the list?", "Explain HPG's setup" |
| `review_quality` | Data quality and pipeline health | "Which candidates have weak data quality?", "Check quality for VNM" |
| `show_lineage` | Data source and scoring lineage | "Where does FPT's score come from?", "Show lineage for HPG" |
| `summarize_watchlist` | High-level watchlist summary | "Summarize today's watchlist", "How many candidates are there?" |
| `create_research_note` | Save a research note to the warehouse | "Note: FPT base is compressing", "Add note for VNM: watch RS" |
| `show_history` | Recent research session history | "Show my recent sessions", "What did I look at last?" |
| `unsupported_or_unsafe` | Blocked — trading, web search, code exec, or unsafe request | "Buy FPT", "Search the web for VNM news" |

---

## Tool Plan and Trace

### What is shown with `--show-plan`

The tool plan is printed in a blue panel before the answer. It shows:

```
Plan for intent: explain_symbol
Steps:
  1. candidate.explain({'symbol': 'FPT', 'date': '2026-07-06'}) — Explain candidate score and evidence
  2. lineage.get_symbol_lineage({'symbol': 'FPT', 'date': '2026-07-06'}) — Retrieve data lineage
  3. quality.get_status({'symbol': 'FPT'}) — Check data quality status
```

For refused requests, the plan shows:

```
[REFUSED] This request involves trading execution, account or allocation management. ...
```

### What is shown with `--trace`

The tool trace summary is printed in a dim panel after the answer. It contains the `tool_trace_summary` field from the synthesized answer, which the LLM generates based on which tools were called and what they returned.

### How to read the plan

- **Step number**: Execution order.
- **Tool name**: The Phase 5.8 allowlisted tool called (e.g. `candidate.explain`).
- **Arguments**: What was passed to the tool (symbol, date, filters, etc.).
- **Purpose**: Human-readable description of why the step is included.

---

## Refusal Policy

The assistant enforces four refusal categories deterministically before any LLM call. Refused requests exit with code 1.

### TRADING_EXECUTION

Any request involving buy, sell, order, broker, account, or allocation management.

```bash
vnalpha ask "Buy FPT"          # → TRADING_EXECUTION
vnalpha ask "Sell my VNM"      # → TRADING_EXECUTION
vnalpha ask "Place an order"   # → TRADING_EXECUTION
```

### UNAVAILABLE_TOOL

Any request requiring web search, Python execution, MCP tool calls, raw SQL, or filesystem access.

```bash
vnalpha ask "Search the web for FPT news"     # → UNAVAILABLE_TOOL
vnalpha ask "Run this Python code for me"     # → UNAVAILABLE_TOOL
vnalpha ask "Execute a raw SQL query"         # → UNAVAILABLE_TOOL
```

### SAFETY_BYPASS

Requests to hide traces, fabricate data, bypass safety controls, or override scores.

```bash
vnalpha ask "Fabricate a score for FPT"       # → SAFETY_BYPASS
vnalpha ask "Hide the trace for this session" # → SAFETY_BYPASS
vnalpha ask "Override FPT's score to 0.99"    # → SAFETY_BYPASS
```

### PREDICTION_CERTAINTY

Requests for guaranteed outcomes or certainty about future price movement.

```bash
vnalpha ask "Will FPT definitely go up?"      # → PREDICTION_CERTAINTY
vnalpha ask "Give me a risk-free trade"       # → PREDICTION_CERTAINTY
```

---

## TUI Usage

Press `a` in the TUI to open the Research Assistant screen.

```
Keyboard shortcut: a
```

### Layout

```
┌─────────────────────────────────────────┐
│ Header                                  │
│ Research Assistant — ask a question...  │
│ [ Input bar                           ] │
│                                         │
│  Answer panel (summary, basis, risks)   │
│                                         │
│  Plan panel (tool steps, dim)           │
│                                         │
│ Footer — Escape: Back                   │
└─────────────────────────────────────────┘
```

### Workflow

1. Press `a` from any screen to push the `AssistantScreen`.
2. Type your question in the input bar and press `Enter`.
3. The answer panel shows "Processing..." while the assistant runs.
4. On success: answer panel shows the summary, basis, and risks. Plan panel shows the tool steps (dim).
5. On refusal: answer panel shows `[red]Refused: <reason>[/red]`.
6. On error: answer panel shows `[red]Error: <message>[/red]`.
7. Press `Escape` to return to the previous screen.

---

## Phase 5.9 Dependency on Phase 5.8 Tool Contracts

Phase 5.9 does not bypass Phase 5.8. The LLM has **no direct access** to the warehouse, no raw SQL, and no filesystem. The only interface is the Phase 5.8 tool registry via the `AssistantExecutor`.

```
User prompt
  → Policy check (deterministic, no LLM)
  → IntentClassifier (LLM classify stage)
  → PlanBuilder (deterministic, maps intent to ToolPlanStep list)
  → AssistantExecutor (calls Phase 5.8 tools only)
      → watchlist.scan / watchlist.filter
      → candidate.explain / candidate.compare
      → quality.get_status
      → lineage.get_symbol_lineage
      → note.create
      → history.list_sessions
  → AnswerSynthesizer (LLM synthesize stage — receives tool outputs as context)
  → AssistantAnswer (grounded in tool output, no fabrication allowed)
```

Every tool in the plan is validated against `TOOL_ALLOWLIST` before execution. Any tool not on the allowlist raises `PlanValidationError`.

Every call is persisted in:
- `assistant_session` — one row per `ask` invocation
- `llm_trace` — one row per LLM stage (classify, synthesize)
- `tool_trace` — one row per tool step executed

---

## Configuration

All settings are controlled via environment variables. The gateway reads them at startup via `LLMGatewayConfig.from_env()`.

| Variable | Default | Description |
|----------|---------|-------------|
| `VNALPHA_LLM_MODEL` | `gpt-4o-mini` | Model identifier sent to the LLM endpoint |
| `VNALPHA_LLM_ENDPOINT` | `https://api.openai.com/v1/chat/completions` | Full URL for the chat completions endpoint |
| `VNALPHA_LLM_API_KEY` | (none) | API key. Falls back to `OPENAI_API_KEY` if not set |
| `VNALPHA_LLM_TIMEOUT` | `30` | HTTP timeout in seconds per attempt |
| `VNALPHA_LLM_MAX_OUTPUT_TOKENS` | `1024` | Maximum tokens in the LLM response |
| `VNALPHA_LLM_STORE_RAW` | `false` | If `1`/`true`/`yes`, store raw prompt/response in traces |

### Example

```bash
export VNALPHA_LLM_MODEL=gpt-4o
export VNALPHA_LLM_API_KEY=sk-...
export VNALPHA_LLM_TIMEOUT=60
vnalpha ask "Explain FPT"
```

---

## Limitations

The following are explicitly **not supported** in Phase 5.9:

| Limitation | Notes |
|------------|-------|
| No web search | Cannot fetch news, prices, or data from external URLs |
| No Python execution | Cannot run arbitrary code, scripts, or notebooks |
| No backtest | Cannot simulate historical strategy returns |
| No MCP tool calls | Model Context Protocol tools are not connected |
| No broker execution | Cannot place, modify, or cancel orders |
| No real-time data | All data comes from the local DuckDB warehouse (sync separately with `vnalpha sync`) |
| No cross-session memory | Each `ask` call is independent; the assistant does not remember previous questions |
| No file system reads | Cannot read or write files outside the warehouse path |
