# Specification: Natural-Language Research Assistant

## Purpose

Define the warehouse-grounded natural-language research assistant for CLI and TUI use.
## Requirements
### Requirement: Assistant shall accept natural-language research prompts

`vnalpha` SHALL provide a natural-language assistant surface for research questions.

The assistant SHALL support CLI and TUI entry points.

The CLI entry point SHALL be:

```bash
vnalpha ask "<natural-language question>"
```

The assistant SHALL create an `assistant_session` for every prompt.

#### Scenario: Ask a research question through CLI

- **GIVEN** the user runs `vnalpha ask "Why is FPT in the watchlist?"`
- **WHEN** the assistant receives the prompt
- **THEN** it SHALL create an `assistant_session`
- **AND** it SHALL classify the prompt intent
- **AND** it SHALL build a tool plan before answering

#### Scenario: Ask a research question through TUI

- **GIVEN** the TUI is open
- **WHEN** the user enters `Compare FPT, VNM, and MWG`
- **THEN** the assistant SHALL process the prompt through the same assistant flow
- **AND** the answer SHALL render in the TUI answer panel

---

### Requirement: Assistant shall classify supported research intents

The assistant SHALL classify user prompts into one of the supported intent families:

```text
scan_candidates
filter_candidates
compare_symbols
explain_symbol
review_quality
show_lineage
summarize_watchlist
create_research_note
show_history
unsupported_or_unsafe
```

The classifier SHALL return:

```text
intent
confidence
entities
needs_clarification
clarification_question
safety_flags
```

Classifier responses SHALL be parsed through a shared JSON parser utility that attempts all supported extraction strategies (markdown fence strip, embedded JSON extraction, strict json.loads).
If the parser still cannot produce a valid payload, it SHALL return a clear invalid-response error and this classification path SHALL retry once with stronger model profile settings.
If the second attempt also fails to parse, the assistant SHALL surface a classifier failure and SHALL NOT continue to planner or synthesis.

#### Scenario: Classify explain intent

- **GIVEN** the prompt `Why is FPT in the watchlist today?`
- **WHEN** the classifier runs
- **THEN** it SHALL classify the prompt as `explain_symbol`
- **AND** it SHALL extract symbol `FPT`

#### Scenario: Classify compare intent

- **GIVEN** the prompt `Compare FPT, VNM, and MWG`
- **WHEN** the classifier runs
- **THEN** it SHALL classify the prompt as `compare_symbols`
- **AND** it SHALL extract symbols `FPT`, `VNM`, and `MWG`

#### Scenario: Classify unsafe intent

- **GIVEN** the prompt `Buy FPT for me now`
- **WHEN** safety precheck or classifier runs
- **THEN** it SHALL classify the prompt as `unsupported_or_unsafe`
- **AND** the assistant SHALL refuse the request

#### Scenario: Recover parser from malformed but recoverable classifier JSON

- **GIVEN** the first classifier response is not clean JSON but contains a JSON object in text
- **WHEN** the parser runs
- **THEN** it SHALL extract and parse the JSON object and continue classification if valid

#### Scenario: Retry when classifier JSON is invalid

- **GIVEN** the first classifier response is not parseable as JSON
- **WHEN** classifier parse fails
- **THEN** the assistant SHALL retry classification once with stronger profile settings
- **AND** if the second response still fails to parse
- **THEN** it SHALL return an explicit invalid-response classifier error
- **AND** no plan SHALL be executed for that turn

### Requirement: Assistant shall build explicit tool plans

For supported intents, the assistant SHALL build an explicit `AssistantPlan` before execution.

The plan SHALL include:

```text
intent
steps
assumptions
required_artifacts
refusal_reason
```

Each step SHALL include:

```text
step_id
tool_name
arguments
purpose
required_permission
```

#### Scenario: Build plan for explain prompt

- **GIVEN** the prompt `Why is FPT in the watchlist today?`
- **WHEN** the planner runs
- **THEN** it SHALL produce a plan that may call:
  - `candidate.explain`
  - `quality.get_status`
  - `lineage.get_symbol_lineage`
- **AND** the plan SHALL include symbol `FPT`

#### Scenario: Build plan for scan prompt

- **GIVEN** the prompt `Show strongest VN30 candidates today`
- **WHEN** the planner runs
- **THEN** it SHALL produce a plan that may call `watchlist.scan`
- **AND** the plan SHALL include universe `VN30`

#### Scenario: Plan preview without execution

- **GIVEN** the user runs `vnalpha ask "Compare FPT and VNM" --no-execute`
- **WHEN** the assistant builds the plan
- **THEN** it SHALL render the plan
- **AND** it SHALL NOT execute any tool

---

### Requirement: Assistant shall execute only allowlisted local tools

The assistant SHALL execute only approved Phase 5.8 local tools.

Initial allowlist:

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

The assistant SHALL NOT execute:

```text
network access
web search
web fetch
Python execution
MCP calls
raw SQL
filesystem access
code mutation
broker tools
account tools
order tools
portfolio tools
```

#### Scenario: Allowed local tool execution

- **GIVEN** a valid plan calls `candidate.compare`
- **WHEN** the executor validates the plan
- **THEN** it SHALL execute the tool
- **AND** persist a tool trace

#### Scenario: Disallowed tool is blocked

- **GIVEN** a plan contains `web.fetch_url`
- **WHEN** Phase 5.9 allowlist validation runs
- **THEN** execution SHALL be blocked
- **AND** the assistant session SHALL be marked refused or validation error

---

### Requirement: Assistant shall ground answers in tool outputs

The assistant SHALL synthesize answers only from executed tool outputs and deterministic persisted artifacts.

The assistant SHALL NOT:

```text
- invent scores
- invent candidate classes
- invent setup types
- invent risk flags
- invent data quality
- invent lineage
- override persisted candidate_score
- present model intuition as a deterministic result
```

#### Scenario: Grounded explanation

- **GIVEN** `candidate.explain` returns score, class, setup, evidence, and risk flags for FPT
- **WHEN** the assistant synthesizes the answer
- **THEN** the answer SHALL reflect those returned values
- **AND** it SHALL not change the score or class

#### Scenario: Missing score data

- **GIVEN** no candidate score exists for XYZ
- **WHEN** the user asks `Why is XYZ in the watchlist?`
- **THEN** the assistant SHALL state that candidate data is missing
- **AND** it SHALL suggest running the relevant Phase 5 pipeline command
- **AND** it SHALL NOT fabricate an explanation

---

### Requirement: Assistant shall persist assistant and model traces

Every assistant request SHALL persist an `assistant_session`.

Model calls SHALL persist `llm_trace` records.

`assistant_session` SHALL include:

```text
assistant_session_id
started_at
finished_at
status
surface
user_prompt
intent
plan_json
answer_json
refusal_reason
error_json
```

`llm_trace` SHALL include:

```text
llm_trace_id
assistant_session_id
stage
model
started_at
finished_at
status
input_summary_json
output_summary_json
usage_json
error_json
```

Raw prompt and response storage SHALL be configurable and SHALL support redaction.

#### Scenario: Persist successful assistant session

- **GIVEN** the user asks `Compare FPT and VNM`
- **WHEN** the assistant completes successfully
- **THEN** an `assistant_session` row SHALL exist with status `SUCCESS`
- **AND** the row SHALL include intent and plan metadata

#### Scenario: Persist refused assistant session

- **GIVEN** the user asks `Place an order for FPT`
- **WHEN** the assistant refuses the request
- **THEN** an `assistant_session` row SHALL exist with status `REFUSED`
- **AND** the row SHALL include refusal_reason

#### Scenario: Persist LLM trace

- **GIVEN** the classifier calls an LLM
- **WHEN** the model call completes
- **THEN** an `llm_trace` row SHALL exist
- **AND** stage SHALL be `classify`
- **AND** usage metadata SHALL be recorded when available

---

### Requirement: Assistant shall expose plan and trace to the user

The assistant SHALL make the plan and tool trace inspectable.

CLI SHALL support:

```text
--show-plan
--trace
--no-execute
```

TUI SHALL provide expandable plan and trace views.

#### Scenario: Show plan

- **GIVEN** the user runs `vnalpha ask "Show strongest candidates" --show-plan`
- **WHEN** the assistant builds the plan
- **THEN** the CLI SHALL display the planned tool calls and arguments

#### Scenario: Show trace

- **GIVEN** the user runs `vnalpha ask "Why is FPT in the watchlist?" --trace`
- **WHEN** the assistant completes
- **THEN** the CLI SHALL display a summary of executed tools

---

### Requirement: Assistant shall support scan and summarize workflows

The assistant SHALL answer natural-language prompts that map to watchlist scan and summary workflows.

#### Scenario: Show strongest candidates

- **GIVEN** a daily watchlist exists
- **WHEN** the user asks `Show strongest candidates today`
- **THEN** the assistant SHALL call `watchlist.scan`
- **AND** return a ranked candidate summary
- **AND** include risks and data-quality caveats when available

#### Scenario: Summarize watchlist

- **GIVEN** a daily watchlist exists
- **WHEN** the user asks `Summarize today's watchlist`
- **THEN** the assistant SHALL summarize candidate classes, setup types, major risk flags, and data-quality issues

---

### Requirement: Assistant shall support symbol explanation workflow

The assistant SHALL answer natural-language prompts that ask why a symbol appears in the watchlist or how it scored.

#### Scenario: Explain symbol

- **GIVEN** FPT has persisted candidate score and evidence
- **WHEN** the user asks `Why is FPT in the watchlist?`
- **THEN** the assistant SHALL return score, class, setup, evidence, risk flags, data quality, and lineage

---

### Requirement: Assistant shall support symbol comparison workflow

The assistant SHALL answer natural-language prompts that compare a small set of symbols.

#### Scenario: Compare symbols

- **GIVEN** FPT, VNM, and MWG have persisted artifacts
- **WHEN** the user asks `Compare FPT, VNM, and MWG`
- **THEN** the assistant SHALL call `candidate.compare`
- **AND** summarize differences in score, class, setup, risk flags, quality, and relative strength fields when available

---

### Requirement: Assistant shall support data quality review workflow

The assistant SHALL answer natural-language prompts about data quality.

#### Scenario: Review quality for one symbol

- **GIVEN** FPT has canonical OHLCV and candidate artifacts
- **WHEN** the user asks `Does FPT have any data quality issue?`
- **THEN** the assistant SHALL call `quality.get_status`
- **AND** report quality status and rejected-symbol records when available

#### Scenario: Review quality for watchlist

- **GIVEN** a daily watchlist exists
- **WHEN** the user asks `Which watchlist candidates have weak data quality?`
- **THEN** the assistant SHALL call quality tools for watchlist members
- **AND** summarize affected candidates

---

### Requirement: Assistant shall support lineage workflow

The assistant SHALL answer natural-language prompts about source lineage.

#### Scenario: Show lineage for symbol

- **GIVEN** FPT has candidate and canonical lineage
- **WHEN** the user asks `Where does FPT data come from?`
- **THEN** the assistant SHALL call `lineage.get_symbol_lineage`
- **AND** return provider, ingestion run, feature date, scoring version, and generated time when available

---

### Requirement: Assistant shall support note and history workflows

The assistant SHALL support note creation and session history through allowlisted tools.

#### Scenario: Create note

- **GIVEN** the user asks `Add a note for FPT: watch relative strength vs VNINDEX`
- **WHEN** the assistant classifies the request
- **THEN** it SHALL call `note.create`
- **AND** persist the note linked to the assistant session

#### Scenario: Show history

- **GIVEN** previous assistant sessions exist
- **WHEN** the user asks `Show my recent research questions`
- **THEN** the assistant SHALL call `history.list_sessions`
- **AND** return recent session summaries

---

### Requirement: Assistant shall refuse unsafe or unsupported requests

The assistant SHALL refuse requests outside the research-only boundary.

It SHALL refuse:

```text
- broker execution
- order placement
- account management
- portfolio management
- buy/sell instruction requests
- guaranteed prediction requests
- requests requiring unavailable web/Python/MCP tools
- requests to hide traces or bypass policy
- requests to fabricate missing data
```

#### Scenario: Refuse order request

- **GIVEN** the user asks `Place a buy order for FPT`
- **WHEN** the assistant precheck runs
- **THEN** the assistant SHALL refuse
- **AND** no tool SHALL execute

#### Scenario: Refuse buy/sell advice request

- **GIVEN** the user asks `Should I buy FPT now?`
- **WHEN** the assistant processes the prompt
- **THEN** it SHALL refuse to give buy/sell advice
- **AND** it MAY offer to show deterministic research artifacts instead

#### Scenario: Refuse unavailable web request

- **GIVEN** controlled retrieval tools are not enabled
- **WHEN** the user asks `Search the web for latest FPT news`
- **THEN** the assistant SHALL refuse or state that web retrieval is not available in this phase
- **AND** it SHALL NOT attempt direct internet access

---

### Requirement: Assistant shall not break Phase 5 and Phase 5.8 surfaces

Adding Phase 5.9 SHALL NOT break existing deterministic commands and command-layer behavior.

Existing surfaces SHALL remain available:

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
vnalpha cmd "..."
```

#### Scenario: Existing command still works

- **GIVEN** Phase 5.9 is enabled
- **WHEN** the user runs `vnalpha cmd "/scan"`
- **THEN** the Phase 5.8 command runner SHALL still work

#### Scenario: Pipeline still works

- **GIVEN** Phase 5.9 is enabled
- **WHEN** the user runs the Phase 5 fixture E2E tests
- **THEN** the tests SHALL pass without regression

---

### Requirement: Current-symbol research dates shall use the versioned market session

Current-symbol research SHALL resolve an omitted date or semantic `today` once
in `Asia/Ho_Chi_Minh` to the latest configured Vietnam trading session on or
before the current date. This policy SHALL apply to CLI ask, TUI defaults,
assistant planning and persistence, deep readiness, `/analyze`,
`/research-plan`, and `/setup-evidence`.

An explicit ISO date SHALL remain explicit after validation. Current-symbol
readiness SHALL own bounded provisioning for the resolved session and SHALL NOT
replace an implicit current-session request with an older warehouse summary
date. The generic `resolve_date` compatibility contract remains unchanged.
Implicit resolution outside the versioned calendar coverage MUST fail closed.

#### Scenario: Weekend current-symbol research uses the preceding session

- **GIVEN** the Vietnam current date is Sunday `2026-07-19`
- **WHEN** a current-symbol research surface receives no date or `today`
- **THEN** the effective target date is Friday `2026-07-17`
- **AND** planning, readiness, audit, persistence and remediation use that same date

#### Scenario: Explicit non-session date remains explicit

- **GIVEN** the user explicitly requests `2026-07-19`
- **WHEN** current-symbol date resolution runs
- **THEN** the effective target date remains `2026-07-19`

#### Scenario: Calendar coverage is unavailable

- **GIVEN** the implicit current date is outside the configured calendar range
- **WHEN** current-symbol date resolution runs
- **THEN** the surface returns a validation or fail-closed readiness result
- **AND** no unconfigured weekday is claimed as a valid market session
