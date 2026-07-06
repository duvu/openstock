# Tasks: Phase 5.8 Research Workspace Command Layer

## 1. Command core

- [ ] 1.1 Add `vnalpha.commands.models` with `ParsedCommand`, `CommandFilter`, `CommandResult`, result table/panel/artifact models, and error model.
- [ ] 1.2 Add `vnalpha.commands.errors` with typed command errors.
- [ ] 1.3 Add `vnalpha.commands.parser` for deterministic slash-command parsing.
- [ ] 1.4 Add unit tests for command names, positional args, filters, options, quoted text, and invalid syntax.
- [ ] 1.5 Add normalization rules for symbols, candidate classes, setup types, and dates.

## 2. Command registry

- [ ] 2.1 Add `CommandRegistry` with explicit command registration.
- [ ] 2.2 Reject unknown commands with `UnknownCommandError`.
- [ ] 2.3 Add command metadata: name, description, usage, examples, handler, permissions.
- [ ] 2.4 Add `/help` command backed by registry metadata.
- [ ] 2.5 Add tests for registry lookup, duplicate registration, and unknown command handling.

## 3. Local tool registry

- [ ] 3.1 Add `vnalpha.tools.models` with `ToolSpec`, `ToolInput`, `ToolOutput`, and `ToolPermission`.
- [ ] 3.2 Add `LocalToolRegistry` with allowlisted tools only.
- [ ] 3.3 Add permission checks for read/write tool classes.
- [ ] 3.4 Add initial local tools:
  - [ ] `watchlist.scan`
  - [ ] `watchlist.filter`
  - [ ] `candidate.explain`
  - [ ] `candidate.compare`
  - [ ] `quality.get_status`
  - [ ] `lineage.get_symbol_lineage`
  - [ ] `note.create`
  - [ ] `history.list_sessions`
- [ ] 3.5 Add tests proving Phase 5.8 tools cannot perform network access, Python execution, MCP calls, code mutation, or broker execution.

## 4. Warehouse schema

- [ ] 4.1 Add `research_session` table to DuckDB schema.
- [ ] 4.2 Add `tool_trace` table to DuckDB schema.
- [ ] 4.3 Add `research_note` table to DuckDB schema.
- [ ] 4.4 Add repository helpers to create/finish sessions and traces.
- [ ] 4.5 Add repository helpers to create/list notes.
- [ ] 4.6 Add migration tests confirming additive tables are created without breaking Phase 5 tables.

## 5. Command handlers

- [ ] 5.1 Implement `/scan` over daily watchlist and candidate scores.
- [ ] 5.2 Implement `/filter` with safe deterministic filter expressions.
- [ ] 5.3 Implement `/compare` for a small list of symbols.
- [ ] 5.4 Implement `/explain` using persisted candidate score, evidence, risk flags, lineage, and data quality.
- [ ] 5.5 Implement `/quality` for symbol-level and watchlist-level data quality.
- [ ] 5.6 Implement `/lineage` for provider, ingestion run, feature date, and scoring version.
- [ ] 5.7 Implement `/note` with persisted research note.
- [ ] 5.8 Implement `/history` for recent research sessions.
- [ ] 5.9 Add integration tests using fixture warehouse data.

## 6. CLI integration

- [ ] 6.1 Add `vnalpha cmd "<slash-command>"`.
- [ ] 6.2 Render command results using Rich tables/panels.
- [ ] 6.3 Return non-zero exit code for parse, validation, permission, or execution errors.
- [ ] 6.4 Persist `research_session` and `tool_trace` for CLI command execution.
- [ ] 6.5 Add CLI contract tests:
  - [ ] `vnalpha cmd "/help"`
  - [ ] `vnalpha cmd "/scan"`
  - [ ] `vnalpha cmd "/explain FPT"`
  - [ ] `vnalpha cmd "/history --limit 20"`

## 7. TUI integration

- [ ] 7.1 Add command input bar to the TUI.
- [ ] 7.2 Add command result panel.
- [ ] 7.3 Show command validation errors without crashing the app.
- [ ] 7.4 Add keyboard shortcut for focusing command input.
- [ ] 7.5 Add command history view or panel.
- [ ] 7.6 Add TUI smoke tests for command input and result panel.

## 8. Safety and product boundary

- [ ] 8.1 Add tests that command handlers do not include broker/order/account/portfolio behavior.
- [ ] 8.2 Add tests that command outputs avoid buy/sell/recommendation language.
- [ ] 8.3 Ensure Phase 5.8 permissions exclude network, Python sandbox, MCP, and code mutation.
- [ ] 8.4 Ensure all `/explain` output is grounded in persisted deterministic artifacts.
- [ ] 8.5 Ensure unsupported commands fail closed.

## 9. Documentation

- [ ] 9.1 Document slash-command grammar.
- [ ] 9.2 Document available commands and examples.
- [ ] 9.3 Document command/session/tool trace tables.
- [ ] 9.4 Document the handoff from Phase 5.8 command tools to Phase 5.9 natural-language assistant.

## 10. Validation

- [ ] 10.1 Run `cd vnalpha && pytest -q`.
- [ ] 10.2 Run command-layer targeted tests.
- [ ] 10.3 Run Phase 5 E2E tests to prove no regression.
- [ ] 10.4 Run TUI smoke tests.
- [ ] 10.5 Manually smoke-test:

```bash
vnalpha cmd "/help"
vnalpha cmd "/scan"
vnalpha cmd "/explain FPT"
vnalpha cmd "/quality FPT"
vnalpha cmd "/lineage FPT"
```
