# Design: Complete R0-R4 Terminal POC

## Design intent

R0-R4 should produce one coherent MVP: a repeatable terminal-first research workspace backed by a local data platform and a persisted analytical warehouse.

The system remains research-only. Deterministic artifacts are the source of truth. LLM output may explain, critique, summarize, plan, or assist with research, but must not create unverified signals, place trades, mutate portfolios, access accounts, or bypass policy.

## Target architecture after this change

```text
┌─────────────────────────────────────────────────────────────┐
│ Host terminal / SSH / tmux                                  │
│                                                             │
│   vnalpha CLI                                               │
│   vnalpha TUI                                               │
│   persistent ChatPanel                                      │
│                                                             │
│   installed from vnalpha.deb                                │
└──────────────────────────────┬──────────────────────────────┘
                               │ reads mostly
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ DuckDB warehouse                                             │
│ /var/lib/openstock/warehouse/warehouse.duckdb                │
│                                                             │
│ canonical_ohlcv, feature_snapshot, candidate_score,          │
│ daily_watchlist, rejected_symbol, outcome tables,            │
│ research_session, tool_trace, assistant_session,             │
│ llm_trace, chat_session, chat_message                        │
└──────────────────────────────▲──────────────────────────────┘
                               │ writes through controlled jobs
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Docker data platform                                         │
│                                                             │
│ vnstock-service  long-running data-only service              │
│ vnalpha-worker   short-lived job runner                      │
│ optional timer   guarded by writer lock                      │
└─────────────────────────────────────────────────────────────┘
```

## Phase boundaries

### R0: deterministic research baseline

R0 owns correctness of the daily research pipeline.

Required flow:

```text
init
sync symbols
sync ohlcv --universe VN30 --start <date>
sync index --symbol VNINDEX --start <date>
build canonical
build features --date <date>
score --date <date>
watchlist --date <date>
```

R0 completion requires both:

1. fixture-backed CI-safe E2E test; and
2. service-backed smoke flow documented and verifiable locally.

The fixture E2E is the non-network correctness gate. The service-backed smoke flow is the operational gate.

### R1: deployment architecture alignment

R1 is complete only when architecture docs match actual files and commands.

Architecture documentation must not describe files, services, launchers, commands, or config paths that do not exist in the implementation unless explicitly marked as planned.

R1 output should include:

- final component responsibilities;
- config path matrix;
- runtime flow;
- DuckDB concurrency rules;
- research-only boundary;
- known limitations.

### R2: deploy and verify

R2 owns repeatability on a fresh host.

The deployment model is intentionally split:

```text
Docker Compose -> data platform and worker jobs
Debian package -> host-native terminal app
DuckDB file    -> shared persisted warehouse
systemd        -> controls long-running data service only
```

The Textual TUI must not be run as a background Docker daemon.

`openstock-verify` is the authoritative readiness check. It should have at least two modes:

```text
openstock-verify
openstock-verify --ci
```

- default mode may check local services and optional smoke data;
- CI mode must not require live provider/network calls beyond local process checks.

### R3: terminal workspace

R3 owns analyst usability in the terminal.

The TUI should be usable as one primary entrypoint rather than forcing the user to switch across many commands.

Minimum layout:

```text
main workspace area
  - watchlist screen
  - symbol detail screen
  - quality screen
  - rejected symbols screen
  - outcomes/calibration screen

persistent bottom/right ChatPanel
  - input bar
  - transcript/log
  - command result summaries
  - trace events
```

R3 does not require the R5 local runtime/server. TUI may still call local Python services directly, but it must avoid long-lived unsafe write connections where possible.

### R4: OpenCode-style chat workspace

R4 turns the chat prototype into a persistent research control panel.

It must not become a free-form agent shell.

Allowed chat capabilities:

```text
read watchlist
read features/scores/evidence
read quality/rejected data
read outcomes/calibration
explain deterministic artifacts
compare symbols
summarize context
create research notes
preview approved pipeline/admin actions
```

Denied capabilities:

```text
broker_order
account_access
portfolio_mutation
margin
transfer
trading
automated_execution
arbitrary_shell
raw_sql_from_prompt
filesystem_write_from_prompt
network_tool_from_prompt
safety_bypass
trace_hiding
fabricated_data
```

## Core implementation decisions

### 1. DuckDB access model

- Pipeline jobs may write.
- TUI should primarily read.
- Chat read commands should use short-lived DB connections.
- Pipeline/admin actions from chat require explicit plan approval.
- Multiple writers must be blocked through a lock.
- Backup should refuse when a writer lock exists unless forced by an explicit operator flag.

### 2. Command execution path

CLI, TUI command screen, ChatPanel slash commands, and assistant tool calls should use the same command/tool execution service.

Anti-pattern to remove:

```text
ChatPanel parses and dispatches commands through a separate path that bypasses command traces, permission checks, or transcript persistence.
```

Target pattern:

```text
input -> parser -> command executor -> permission evaluator -> tool executor -> trace persistence -> result renderer
```

### 3. Transcript persistence

Every chat turn should produce `chat_message` rows.

Minimum metadata:

```text
chat_session_id
role
content
message_type
assistant_session_id when applicable
research_session_id when applicable
tool_trace_ids_json when applicable
plan_json when applicable
metadata_json
```

A new TUI session should create or resume a `chat_session` for the target date.

### 4. Deterministic context

Chat context should be derived from persisted and deterministic state, not hidden model memory.

Context may include:

```text
target_date
selected symbol
last watchlist date
last command
last compared symbols
last plan
visible screen
recent tool traces
```

### 5. Plan approval

Pipeline/admin actions initiated from chat must use a preview/approval flow:

```text
plan created -> preview rendered -> user approves/cancels -> execution -> trace -> persisted result
```

Read-only research commands do not need approval.

### 6. Verification and closure

Task completion must be backed by at least one of:

- code path;
- automated test;
- runnable script;
- manual smoke checklist with concrete commands.

Checked boxes in OpenSpec task files are not sufficient evidence by themselves.

## File layout to implement or align

```text
docker-compose.yml
vnalpha/Dockerfile
packaging/vnalpha/build-deb.sh
packaging/vnalpha/debian/
packaging/vnalpha/vnalpha.env
packaging/openstock/openstock.env
packaging/systemd/openstock-data-platform.service
packaging/systemd/openstock-daily-pipeline.service
packaging/systemd/openstock-daily-pipeline.timer
scripts/openstock-verify
scripts/openstock-backup-warehouse
scripts/openstock-run-pipeline
scripts/openstock-writer-lock
vnalpha/tests/test_phase5_e2e.py
vnalpha/tests/test_tui_smoke.py
vnalpha/tests/test_chat_workspace.py
vnalpha/tests/test_deploy_verify_helpers.py
vnalpha/docs/11-deployment-architecture.md
vnalpha/docs/12-operator-runbook.md
```

Exact paths may vary, but the implementation must keep packaging, scripts, docs, and tests discoverable from the repository root.

## Testing strategy

### Unit tests

- command parser and command registry;
- universe resolution;
- date resolution;
- scoring ontology persistence guard;
- feature status taxonomy;
- policy hard-deny rules;
- verify helper functions;
- writer lock helper functions.

### Fixture E2E tests

- no provider/network dependency;
- isolated temporary or in-memory DuckDB;
- fixture VNINDEX plus at least three equities;
- one strong candidate;
- one weak/ignored candidate;
- one poor-quality or insufficient-history candidate;
- assert features, scores, watchlist, quality/rejection behavior.

### TUI tests

- app construction;
- major screen imports;
- navigation actions;
- watchlist empty-state;
- detail screen empty-state;
- ChatPanel construction;
- non-interactive entrypoint/import check.

### Deployment tests

- `docker compose config`;
- worker image build or CI-safe syntax check;
- `vnalpha --help` after package build/install where environment allows;
- `openstock-verify --ci`;
- shell script syntax checks.

## Migration and compatibility

Existing DuckDB files may lack columns introduced in later R0-R4 hardening.

Migrations must use idempotent patterns such as:

```sql
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...
```

Schema changes should be safe for existing local POC warehouses.

## Security and safety model

The system must remain local-first and research-only.

Required controls:

- localhost-only service binding by default;
- forbidden endpoint checks;
- no credentials or token material returned by service endpoints;
- no account/order/portfolio/margin/transfer/trading commands;
- assistant refusal for execution-oriented prompts;
- no arbitrary shell or raw SQL from chat;
- trace visibility must not be suppressible by prompt.

## Completion rule

R0-R4 are complete only when:

1. all required implementation tasks are done;
2. automated tests pass;
3. deploy verification passes;
4. operator runbook matches actual commands;
5. known limitations are documented;
6. no prohibited trading/execution surface exists.
