# Design: Completion Gate for Phases 5.8, 5.9, and 6

## Current state summary

The current codebase contains meaningful implementations for all three phases:

```text
Phase 5.8
- `vnalpha cmd` command runner exists.
- command parser, registry, handlers, models, and renderers exist.
- `research_session`, `tool_trace`, and `research_note` tables exist.
- TUI command screen exists.

Phase 5.9
- `vnalpha ask` exists.
- AssistantApp, IntentClassifier, PlanBuilder, AssistantExecutor, AnswerSynthesizer exist.
- assistant_session and llm_trace tables exist.
- TUI assistant screen exists.

Phase 6
- outcome schema exists.
- candidate evaluator, horizon selection, metrics, repositories, aggregations, calibration report exist.
- outcome CLI subcommands exist.
- TUI Outcome Review screen exists.
```

However, completion should be based on behavior and tests, not file existence.

## Completion architecture

### Shared command execution service

Phase 5.8 should have one command execution path shared by CLI and TUI:

```text
raw command text
→ create research_session
→ parse command
→ validate command
→ registry dispatch
→ LocalToolRegistry call
→ create/finish tool_trace for each tool call
→ CommandResult
→ finish research_session
→ renderer
```

This avoids divergence between CLI and TUI.

### Tool execution boundary

Command handlers and assistant executor should call tools through a registry/executor boundary:

```text
Command/Assistant plan
→ LocalToolRegistry
→ permission check
→ traced execution
→ ToolOutput
```

Direct calls to `vnalpha.tools.*` from command handlers should be removed or wrapped so they cannot bypass permission checks and trace persistence.

### Assistant boundary

Phase 5.9 should remain above Phase 5.8 tools:

```text
natural-language prompt
→ assistant_session
→ policy precheck
→ intent classification
→ plan builder
→ allowlist validation
→ traced local tool execution
→ grounded synthesis
→ final answer
```

The LLM may classify and synthesize. It must not directly query the database, call arbitrary code, use web retrieval, or produce independent signals.

### Outcome evaluation boundary

Phase 6 should make user-facing evaluation complete in one command path:

```text
vnalpha outcome evaluate --date D
→ evaluate candidate_outcome for all horizons
→ aggregate watchlist_outcome
→ aggregate score_bucket_performance
→ aggregate setup_type_performance
→ aggregate risk_flag_performance
→ produce summary
```

Reports and TUI screens should not require a hidden manual aggregation step after candidate evaluation.

## Main design changes required

### 1. CommandExecutor

Add a command-layer execution service:

```text
vnalpha/src/vnalpha/commands/executor.py
```

Responsibilities:

```text
- create research_session before parsing where possible.
- parse and validate commands.
- map parse/validation/unknown errors to VALIDATION_ERROR.
- dispatch registered handler.
- expose tool executor or registry to handlers.
- finish session with SUCCESS, FAILED, or VALIDATION_ERROR.
```

CLI and TUI should both use this service.

### 2. TracedLocalToolExecutor

Add a thin executor around LocalToolRegistry:

```text
vnalpha/src/vnalpha/tools/executor.py
```

Responsibilities:

```text
- accept tool_name, permission, args, session_id, optional assistant_session_id.
- create tool_trace before tool call.
- finish tool_trace on success/failure.
- enforce permission checks.
- refuse forbidden permissions.
```

### 3. Tool trace schema disambiguation

Current `tool_trace.session_id` is sufficient for Phase 5.8 command sessions, but ambiguous for Phase 5.9 assistant sessions.

Recommended additive schema:

```text
tool_trace
├── session_id nullable              # research_session id
├── assistant_session_id nullable    # assistant_session id
└── trace_parent_type                # command | assistant
```

MVP alternative: keep `session_id` but document and test that assistant ids are stored there. Preferred: add explicit `assistant_session_id` to avoid ambiguity.

### 4. Command handlers use tool executor

Handlers should not import tool implementations directly.

Current pattern to replace:

```python
from vnalpha.tools.watchlist import scan_watchlist
output = scan_watchlist(conn, date=date)
```

Target pattern:

```python
output = tool_executor.call("watchlist.scan", date=date)
```

### 5. Command behavior fixes

Required command fixes:

```text
/scan
- resolve named universe instead of treating it as display-only.
- render risk_flags.

/filter
- validate allowed fields.
- reject unknown fields as VALIDATION_ERROR.
- reject malformed filter values for numeric operators.

/compare
- include risk flags, data quality, and relative strength fields when available.

/explain
- include data quality panel.

/quality
- include rejected_symbol records for symbol-level quality.
```

### 6. Assistant hardening

Required assistant fixes:

```text
- tests must use FakeLLMClient; normal test runs must not require external LLM credentials.
- capture model name and usage where available in llm_trace.
- make plan and trace output stable for CLI `--show-plan` and `--trace`.
- ensure no_execute does not execute tools or create tool_trace.
- ensure refused prompts create assistant_session with REFUSED and no tool_trace.
- ensure tool outputs are included in answer grounding or trace references.
```

### 7. Outcome aggregation path

Required Phase 6 fixes:

```text
- `evaluate_watchlist_date` or CLI `outcome evaluate` must call aggregate_all for every horizon after candidate outcomes are persisted.
- `outcome report` should either use existing aggregates or compute missing aggregates before rendering.
- CLI output should show candidate counts plus aggregate counts.
- TUI OutcomeScreen should avoid duplicate DataTable column addition in no-data paths.
- outcome date/horizon labels should say sessions, not days.
```

## Testing strategy

### Phase 5.8 tests

```text
parser rejects malformed filters
unknown command persists VALIDATION_ERROR
CLI cmd creates research_session
CLI cmd creates tool_trace for each local tool
TUI command execution creates research_session with surface=tui
/scan VN30 filters or resolves named universe
/scan renders risk_flags
/filter rejects unknown field
/compare includes required fields
/explain includes data quality
/quality includes rejected_symbol records
```

### Phase 5.9 tests

```text
ask command exists
assistant_session created for every prompt
llm_trace created for classify and synthesize
FakeLLMClient can drive scan/explain/compare/quality/lineage/note/history workflows
--no-execute creates no tool_trace
--show-plan renders plan
--trace renders executed tool summary
unsafe prompts are refused before tool execution
answers do not override tool output score/class/setup/quality
```

### Phase 6 tests

```text
migrations create all outcome tables
candidate_outcome generated for complete, pending, partial, missing-data cases
forward_return and excess_return formulas are correct
max_gain and max_drawdown are correct
hit/failure classification is correct
outcome evaluate generates candidate and aggregate tables
outcome report works after evaluate without extra manual steps
TUI OutcomeScreen handles no-data and data states
Phase 5 E2E still passes
```

## Completion decision rule

A phase can be marked complete only when:

```text
- all corresponding targeted tests pass.
- manual smoke commands pass.
- no high-severity mismatch remains.
- safety boundary tests pass.
```
