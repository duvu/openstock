# Tasks: Phase 5.8 Research Workspace Command Layer

## 1. Command core

- [x] 1.1 Add `vnalpha.commands.models` with `ParsedCommand`, `CommandFilter`, `CommandResult`, result table/panel/artifact models, and error model.
- [x] 1.2 Add `vnalpha.commands.errors` with typed command errors.
- [x] 1.3 Add `vnalpha.commands.parser` for deterministic slash-command parsing.
- [x] 1.4 Add unit tests for command names, positional args, filters, options, quoted text, and invalid syntax.
- [x] 1.5 Add normalization rules for symbols, candidate classes, setup types, and dates.

## 2. Command registry

- [x] 2.1 Add `CommandRegistry` with explicit command registration.
- [x] 2.2 Reject unknown commands with `UnknownCommandError`.
- [x] 2.3 Add command metadata: name, description, usage, examples, handler, permissions.
- [x] 2.4 Add `/help` command backed by registry metadata.
- [x] 2.5 Add tests for registry lookup, duplicate registration, and unknown command handling.

## 3. Local tool registry

- [x] 3.1 Add `vnalpha.tools.models` with `ToolSpec`, `ToolInput`, `ToolOutput`, and `ToolPermission`.
- [x] 3.2 Add `LocalToolRegistry` with allowlisted tools only.
- [x] 3.3 Add permission checks for read/write tool classes.
- [x] 3.4 Add initial local tools:
  - [x] `watchlist.scan`
  - [x] `watchlist.filter`
  - [x] `candidate.explain`
  - [x] `candidate.compare`
  - [x] `quality.get_status`
  - [x] `lineage.get_symbol_lineage`
  - [x] `note.create`
  - [x] `history.list_sessions`
- [x] 3.5 Add tests proving Phase 5.8 tools cannot perform network access, Python execution, MCP calls, code mutation, or broker execution.

## 4. Warehouse schema

- [x] 4.1 Add `research_session` table to DuckDB schema.
- [x] 4.2 Add `tool_trace` table to DuckDB schema.
- [x] 4.3 Add `research_note` table to DuckDB schema.
- [x] 4.4 Add repository helpers to create/finish sessions and traces.
- [x] 4.5 Add repository helpers to create/list notes.
- [x] 4.6 Add migration tests confirming additive tables are created without breaking Phase 5 tables.

## 5. Command handlers

- [x] 5.1 Implement `/scan` over daily watchlist and candidate scores.
- [x] 5.2 Implement `/filter` with safe deterministic filter expressions.
- [x] 5.3 Implement `/compare` for a small list of symbols.
- [x] 5.4 Implement `/explain` using persisted candidate score, evidence, risk flags, lineage, and data quality.
- [x] 5.5 Implement `/quality` for symbol-level and watchlist-level data quality.
- [x] 5.6 Implement `/lineage` for provider, ingestion run, feature date, and scoring version.
- [x] 5.7 Implement `/note` with persisted research note.
- [x] 5.8 Implement `/history` for recent research sessions.
- [x] 5.9 Add integration tests using fixture warehouse data.

## 6. CLI integration

- [x] 6.1 Add `vnalpha cmd "<slash-command>"`.
- [x] 6.2 Render command results using Rich tables/panels.
- [x] 6.3 Return non-zero exit code for parse, validation, permission, or execution errors.
- [x] 6.4 Persist `research_session` and `tool_trace` for CLI command execution.
- [x] 6.5 Add CLI contract tests:
  - [x] `vnalpha cmd "/help"`
  - [x] `vnalpha cmd "/scan"`
  - [x] `vnalpha cmd "/explain FPT"`
  - [x] `vnalpha cmd "/history --limit 20"`

## 7. TUI integration

- [x] 7.1 Add command input bar to the TUI.
- [x] 7.2 Add command result panel.
- [x] 7.3 Show command validation errors without crashing the app.
- [x] 7.4 Add keyboard shortcut for focusing command input.
- [x] 7.5 Add command history view or panel.
- [x] 7.6 Add TUI smoke tests for command input and result panel.

## 8. Safety and product boundary

- [x] 8.1 Add tests that command handlers do not include broker/order/account/portfolio behavior.
- [x] 8.2 Add tests that command outputs avoid buy/sell/recommendation language.
- [x] 8.3 Ensure Phase 5.8 permissions exclude network, Python sandbox, MCP, and code mutation.
- [x] 8.4 Ensure all `/explain` output is grounded in persisted deterministic artifacts.
- [x] 8.5 Ensure unsupported commands fail closed.

## 9. Documentation

- [x] 9.1 Document slash-command grammar.
- [x] 9.2 Document available commands and examples.
- [x] 9.3 Document command/session/tool trace tables.
- [x] 9.4 Document the handoff from Phase 5.8 command tools to Phase 5.9 natural-language assistant.

## 10. Validation

- [x] 10.1 Run `cd vnalpha && pytest -q`.
- [x] 10.2 Run command-layer targeted tests.
- [x] 10.3 Run Phase 5 E2E tests to prove no regression.
- [x] 10.4 Run TUI smoke tests.
- [x] 10.5 Manually smoke-test:

```bash
vnalpha cmd "/help"
vnalpha cmd "/scan"
vnalpha cmd "/explain FPT"
vnalpha cmd "/quality FPT"
vnalpha cmd "/lineage FPT"
```
