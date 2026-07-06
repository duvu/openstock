# Design: Phase 5.9 Natural-Language Research Assistant

## Context

Phase 5.9 adds a natural-language research assistant on top of Phase 5.8 command/tool contracts.

The assistant does not replace the deterministic pipeline. It routes user intent to approved tools and explains returned artifacts.

```text
Natural-language prompt
→ Assistant Session
→ Intent Classifier
→ Plan Builder
→ Tool Allowlist
→ Tool Executor
→ Grounded Answer Synthesizer
→ Answer + Plan Trace + Tool Trace
```

## Design principles

### LLM is subordinate to deterministic artifacts

The assistant can plan, call tools, explain, critique, and summarize. It must not create final scoring signals outside persisted deterministic artifacts.

### Natural language compiles to tool calls

A user prompt should become an explicit plan:

```text
intent
required tools
arguments
expected evidence
refusal checks
```

The plan must be inspectable.

### Fail closed

Unsupported intents, ambiguous dangerous requests, or requests requiring unavailable tools must fail closed with a clear refusal or limitation message.

### No direct access to raw capabilities

The LLM must not access raw SQL, filesystem, Python execution, web fetch, MCP, broker, account, order, or portfolio capabilities.

### Ground every answer

Every factual answer about a symbol, score, setup, risk flag, quality state, or lineage must be grounded in tool outputs.

## Proposed module layout

```text
vnalpha/src/vnalpha/assistant/
├── __init__.py
├── app.py
├── prompts.py
├── models.py
├── errors.py
├── intent.py
├── planner.py
├── executor.py
├── synthesizer.py
├── policy.py
├── trace.py
└── renderers/
    ├── rich_renderer.py
    └── textual_renderer.py

vnalpha/src/vnalpha/assistant/intents/
├── scan_candidates.py
├── filter_candidates.py
├── compare_symbols.py
├── explain_symbol.py
├── review_quality.py
├── show_lineage.py
├── summarize_watchlist.py
├── create_research_note.py
├── show_history.py
└── unsupported_or_unsafe.py
```

## Assistant flow

```text
1. Receive user prompt.
2. Create assistant_session row with status RUNNING.
3. Apply safety precheck.
4. Classify intent.
5. Build a tool plan.
6. Validate plan against allowlist and permissions.
7. Execute tools through the Phase 5.8 local tool registry.
8. Persist every tool call in tool_trace.
9. Synthesize final answer from tool outputs only.
10. Persist assistant trace and final answer.
11. Mark assistant_session SUCCESS, REFUSED, VALIDATION_ERROR, or FAILED.
```

## Data model

### `assistant_session`

Records one natural-language user request.

Suggested fields:

```text
assistant_session_id   VARCHAR PRIMARY KEY
started_at             TIMESTAMPTZ NOT NULL
finished_at            TIMESTAMPTZ
status                 VARCHAR NOT NULL
surface                VARCHAR NOT NULL        # cli | tui
user_prompt            VARCHAR NOT NULL
intent                 VARCHAR
plan_json              VARCHAR
answer_json            VARCHAR
refusal_reason         VARCHAR
error_json             VARCHAR
```

### `llm_trace`

Records model calls used for classification, planning, and synthesis.

Suggested fields:

```text
llm_trace_id           VARCHAR PRIMARY KEY
assistant_session_id   VARCHAR NOT NULL
stage                  VARCHAR NOT NULL        # classify | plan | synthesize
model                  VARCHAR
started_at             TIMESTAMPTZ NOT NULL
finished_at            TIMESTAMPTZ
status                 VARCHAR NOT NULL
input_summary_json     VARCHAR
output_summary_json    VARCHAR
usage_json             VARCHAR
error_json             VARCHAR
```

Raw prompt/response capture should be configurable. If stored, it must be explicitly enabled and redaction policy must apply.

### Link to `research_session` and `tool_trace`

Phase 5.9 MAY either:

```text
Option A: reuse research_session for every executed command-equivalent plan step.
Option B: create assistant_session as parent and link tool_trace directly to assistant_session.
```

Recommended MVP: introduce `assistant_session` as parent, and extend `tool_trace` with optional `assistant_session_id`.

## Intent model

Supported intents:

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

Intent output:

```python
class IntentResult:
    intent: str
    confidence: float
    entities: dict[str, Any]
    needs_clarification: bool
    clarification_question: str | None
    safety_flags: list[str]
```

## Plan model

```python
class AssistantPlan:
    intent: str
    steps: list[ToolPlanStep]
    assumptions: list[str]
    required_artifacts: list[str]
    refusal_reason: str | None
```

```python
class ToolPlanStep:
    step_id: str
    tool_name: str
    arguments: dict[str, Any]
    purpose: str
    required_permission: str
```

## Tool allowlist

Phase 5.9 may call only Phase 5.8 deterministic local tools.

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

Explicitly disallowed in Phase 5.9:

```text
network access
web search
web fetch
Python execution
MCP calls
raw SQL execution
filesystem access
codebase mutation
broker/account/order/portfolio tools
```

Future retrieval tools may be added only after the controlled retrieval phase defines their permissions and staging/citation model.

## Prompt boundaries

System prompt should encode:

```text
You are a research assistant for vnalpha.
You must ground answers in tool outputs.
You must not generate independent trading signals.
You must not give buy/sell/order/portfolio advice.
You must not override deterministic scores or candidate classes.
You must not call tools outside the allowlist.
If data is missing, state what is missing and suggest the relevant pipeline command.
```

The assistant must treat tool outputs as higher priority than model intuition.

## Answer synthesis

Answer format should include:

```text
summary
basis / evidence
risks / caveats
tool trace summary
missing data if any
```

For symbol-level answers, include where available:

```text
symbol
score
candidate_class
setup_type
score breakdown
risk_flags
data_quality_status
lineage
```

The assistant must not claim certainty. It may say:

```text
Based on the latest persisted score and feature snapshot...
The deterministic scoring engine classifies this as...
The main risk flags are...
Data quality status is...
```

It must not say:

```text
This stock will go up.
Buy this.
Sell this.
This is guaranteed.
```

## CLI integration

Add:

```bash
vnalpha ask "<natural-language question>"
```

Examples:

```bash
vnalpha ask "Show strongest VN30 candidates today"
vnalpha ask "Why is FPT in the watchlist?"
vnalpha ask "Compare FPT, VNM, and MWG"
vnalpha ask "Which candidates have weak data quality?"
```

CLI behavior:

```text
- create assistant_session
- classify intent
- show plan when --show-plan is enabled
- execute allowlisted tools
- render final answer with Rich
- show trace summary when --trace is enabled
- return non-zero on refused/failed requests if configured
```

## TUI integration

The existing command input can support natural-language mode, or a separate assistant input can be added.

Required behavior:

```text
- user can submit a natural-language research prompt.
- assistant answer appears in a result panel.
- plan and tool trace can be expanded.
- refused requests show a clear policy/permission explanation.
- TUI remains usable after assistant errors.
```

## Refusal policy

The assistant SHALL refuse:

```text
- order placement or execution
- account management
- portfolio management
- broker API use
- buy/sell instruction requests
- guaranteed prediction requests
- requests requiring unavailable web/Python/MCP tools
- requests to hide traces or bypass safety boundaries
- requests to fabricate missing data
```

Refusal should be concise and may redirect to allowed research actions.

## Missing-data behavior

If required data is missing, the assistant should not fabricate.

Examples:

```text
No candidate_score found for FPT on 2026-07-06. Run `vnalpha score --date 2026-07-06` first.
No data-quality status available for MWG. Run sync/build canonical first.
```

## Testing strategy

### Unit tests

```text
intent classification fixtures
planner output validation
tool allowlist enforcement
unsafe request refusal
missing data response policy
answer synthesis from tool outputs
```

### Integration tests

```text
ask strongest candidates
ask explain symbol
ask compare symbols
ask quality review
ask lineage
ask note creation
ask history
unsafe request refusal
unsupported web/Python/MCP request refusal
```

### Trace tests

```text
assistant_session is persisted
llm_trace is persisted for model stages
tool_trace is persisted for executed tools
final answer includes trace summary or trace reference
```

## Migration strategy

Additive DuckDB migration:

```text
assistant_session
llm_trace
```

Optionally extend `tool_trace`:

```text
assistant_session_id nullable
```

No existing Phase 5 or Phase 5.8 table should be broken.

## Compatibility

Phase 5.9 must not break existing surfaces:

```text
vnalpha init
vnalpha sync ...
vnalpha build ...
vnalpha score
vnalpha watchlist
vnalpha tui
vnalpha cmd "..."
```

It adds:

```text
vnalpha ask "..."
```

and TUI assistant prompt support.
