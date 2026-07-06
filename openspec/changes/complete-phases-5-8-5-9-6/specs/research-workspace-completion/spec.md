# Specification: Research Workspace Completion Gate

## ADDED Requirements

### Requirement: Phase 5.8 command execution shall be consistent across CLI and TUI

`vnalpha` SHALL execute Phase 5.8 slash commands through one shared execution service.

The execution service SHALL:

```text
- create research_session records.
- parse slash commands.
- map parse/validation/unknown-command failures to VALIDATION_ERROR.
- dispatch only registered commands.
- execute local tools through traced tool execution.
- finish research_session with SUCCESS, FAILED, or VALIDATION_ERROR.
```

#### Scenario: CLI command creates session and trace

- **GIVEN** the user runs `vnalpha cmd "/scan VN30"`
- **WHEN** the command succeeds
- **THEN** a `research_session` row SHALL exist with surface `cli`
- **AND** at least one `tool_trace` row SHALL exist for the command.

#### Scenario: TUI command creates session and trace

- **GIVEN** the TUI Command screen is open
- **WHEN** the user submits `/quality FPT`
- **THEN** a `research_session` row SHALL exist with surface `tui`
- **AND** at least one `tool_trace` row SHALL exist for the command.

#### Scenario: Unknown command is validation error

- **GIVEN** the user runs `vnalpha cmd "/unknown"`
- **WHEN** the command runner handles the request
- **THEN** a `research_session` row SHALL exist
- **AND** status SHALL be `VALIDATION_ERROR`
- **AND** no local tool SHALL execute.

---

### Requirement: Phase 5.8 command tools shall be executed through LocalToolRegistry

Command handlers SHALL NOT call tool implementations directly.

All command tool calls SHALL pass through:

```text
LocalToolRegistry
permission check
traced execution
ToolOutput
```

#### Scenario: Permission check is enforced

- **GIVEN** a command handler attempts to call a forbidden tool permission
- **WHEN** traced local tool execution runs
- **THEN** the call SHALL fail
- **AND** a failed `tool_trace` row SHALL be persisted.

#### Scenario: Direct tool bypass is not allowed

- **GIVEN** command handlers are inspected
- **WHEN** Phase 5.8 completion tests run
- **THEN** handlers SHALL not bypass the command-layer tool executor for registered command actions.

---

### Requirement: Phase 5.8 command behavior shall match the command spec

Phase 5.8 commands SHALL meet the command output and validation contract.

Required fixes:

```text
/scan renders risk_flags and handles VN30 as real universe filtering or removes universe syntax.
/filter rejects malformed filters and unsupported fields.
/compare includes risk flags, data quality, and relative strength fields when available.
/explain includes data quality.
/quality SYMBOL includes rejected_symbol records.
```

#### Scenario: Malformed filter is rejected

- **GIVEN** the user runs `/filter score>>0.70`
- **WHEN** the parser validates the command
- **THEN** the command SHALL fail with `CommandParseError` or `CommandValidationError`
- **AND** no local tool SHALL execute.

#### Scenario: Unsafe filter field is rejected

- **GIVEN** the user runs `/filter raw_sql="drop table candidate_score"`
- **WHEN** the filter validator runs
- **THEN** the command SHALL fail with `VALIDATION_ERROR`
- **AND** no user-derived raw SQL SHALL execute.

#### Scenario: Scan includes risk flags

- **GIVEN** a daily watchlist exists
- **WHEN** the user runs `/scan`
- **THEN** the result table SHALL include risk flags.

---

### Requirement: Phase 5.9 assistant shall be testable without external LLM access

Phase 5.9 SHALL support deterministic tests with a fake/stub LLM client.

Normal test runs SHALL NOT require:

```text
VNALPHA_LLM_API_KEY
OPENAI_API_KEY
external network access
```

#### Scenario: Fake LLM drives scan workflow

- **GIVEN** a fake LLM returns intent `scan_candidates`
- **WHEN** the test calls assistant flow
- **THEN** the assistant SHALL build a scan plan
- **AND** execute only allowlisted local tools.

#### Scenario: Fake LLM drives explain workflow

- **GIVEN** a fake LLM returns intent `explain_symbol` with symbol `FPT`
- **WHEN** the assistant flow runs
- **THEN** the assistant SHALL call candidate, lineage, and quality tools according to plan.

---

### Requirement: Phase 5.9 assistant shall persist unambiguous traces

Every assistant prompt SHALL create `assistant_session`.

Every LLM call SHALL create `llm_trace`.

Every executed assistant tool call SHALL create `tool_trace` linked unambiguously to the assistant session.

#### Scenario: Assistant prompt creates session and LLM traces

- **GIVEN** the user runs `vnalpha ask "Why is FPT in the watchlist?"`
- **WHEN** the assistant completes
- **THEN** an `assistant_session` row SHALL exist
- **AND** `llm_trace` rows SHALL exist for classification and synthesis.

#### Scenario: Assistant tool trace has assistant parent

- **GIVEN** an assistant plan executes `candidate.explain`
- **WHEN** the tool trace is persisted
- **THEN** the trace SHALL identify the assistant session parent unambiguously.

#### Scenario: No-execute creates no tool trace

- **GIVEN** the user runs `vnalpha ask "Compare FPT and VNM" --no-execute`
- **WHEN** the assistant returns a plan preview
- **THEN** no local tool SHALL execute
- **AND** no tool_trace rows SHALL be created for that session.

---

### Requirement: Phase 5.9 assistant shall enforce research-only policy

The assistant SHALL refuse unsafe or unsupported requests before tool execution.

It SHALL refuse:

```text
broker execution
order placement
account management
portfolio management
buy/sell instruction requests
guaranteed prediction requests
unavailable web/Python/MCP/filesystem/raw-SQL requests
trace hiding or safety bypass requests
data fabrication requests
```

#### Scenario: Trading-like request is refused

- **GIVEN** the user asks `Buy FPT now`
- **WHEN** assistant policy runs
- **THEN** the assistant SHALL return a refusal
- **AND** no local tool SHALL execute
- **AND** the assistant_session SHALL be marked `REFUSED`.

#### Scenario: Grounded answer does not override tool output

- **GIVEN** tool output returns score `0.72` and class `STRONG_CANDIDATE`
- **WHEN** the assistant synthesizes an answer
- **THEN** the answer SHALL not change that score or class.

---

### Requirement: Phase 6 outcome evaluate shall produce both candidate and aggregate outcomes

`vnalpha outcome evaluate` SHALL produce all outcome artifacts needed by review commands, reports, and TUI.

For each evaluated watchlist date and horizon, the command SHALL produce:

```text
candidate_outcome
watchlist_outcome
score_bucket_performance
setup_type_performance
risk_flag_performance
```

#### Scenario: Evaluate date generates aggregates

- **GIVEN** a watchlist exists for `2026-07-06`
- **WHEN** the user runs `vnalpha outcome evaluate --date 2026-07-06`
- **THEN** candidate outcomes SHALL be persisted
- **AND** watchlist, score bucket, setup type, and risk flag aggregate rows SHALL be persisted.

#### Scenario: Report works after evaluate

- **GIVEN** the user has run `vnalpha outcome evaluate --date 2026-07-06`
- **WHEN** the user runs `vnalpha outcome report --horizon 20`
- **THEN** the report SHALL render available aggregate data without requiring a hidden manual aggregation step.

---

### Requirement: Phase 6 outcome UI shall handle data and no-data states safely

CLI and TUI outcome surfaces SHALL handle missing data without crashing.

The UI SHALL use `sessions` terminology for horizons, not calendar-day wording.

#### Scenario: TUI Outcome Review no-data state

- **GIVEN** no outcome data exists
- **WHEN** the user opens Outcome Review
- **THEN** the screen SHALL display a no-data message
- **AND** SHALL remain usable
- **AND** SHALL NOT attempt invalid duplicate column additions.

#### Scenario: Outcome labels use sessions

- **GIVEN** horizon is 20
- **WHEN** CLI or TUI renders the outcome label
- **THEN** the label SHALL say `20 sessions` rather than `20d` unless it explicitly explains that sessions are trading bars.

---

### Requirement: Completion shall be proven by targeted tests

Phases 5.8, 5.9, and 6 SHALL not be marked complete without targeted tests.

Required test groups:

```text
Phase 5.8 parser/registry/executor/trace/CLI/TUI tests
Phase 5.9 assistant policy/planner/executor/synthesizer/trace/CLI/TUI tests
Phase 6 evaluator/metrics/aggregations/report/CLI/TUI tests
Phase 5 regression E2E tests
safety wording tests
```

#### Scenario: Full vnalpha suite passes

- **GIVEN** the completion fixes are implemented
- **WHEN** `cd vnalpha && pytest -q` runs
- **THEN** all tests SHALL pass.

#### Scenario: Safety wording test passes

- **GIVEN** command, assistant, and outcome outputs are generated
- **WHEN** safety wording tests inspect them
- **THEN** they SHALL not contain broker/order/account/portfolio/buy/sell execution language.
