# Design: R0-R4 >90 gap closure

## Design intent

This change turns the current partial R0-R4 implementation into an evidence-backed MVP closure candidate. The target is not theoretical completeness. The target is operational confidence above 90% for each phase through code, tests, scripts, and validation artifacts.

The system remains:

```text
local-first
terminal-first
research-only
single-host POC
DuckDB-backed
no R5 runtime/server dependency
```

## Completion model

Each phase gets a completion score only from evidence:

```text
implementation evidence      code or script exists
unit evidence                focused tests exist
integration evidence         component boundary tests exist
runtime evidence             command output or validation log exists
documentation evidence       docs match actual commands/files
negative evidence            restricted behavior is tested to fail closed
```

A phase can exceed 90% only if at least four evidence types exist, and no blocker remains open.

## Target evidence by phase

```text
R0: implementation + unit + fixture E2E + CLI smoke + docs
R1: docs + file/path alignment + known limitations + completion matrix + validation report
R2: implementation + static CI checks + deployed-host checks + package proof + rollback/backup proof
R3: implementation + TUI pilot/integration tests + empty-state tests + manual smoke proof
R4: implementation + controller wiring + persistence tests + plan/trace tests + restricted-action tests
```

## R0 design

### Current shape

R0 already has a deterministic pipeline:

```text
vnalpha init
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start <date>
vnalpha sync index --symbol VNINDEX --start <date>
vnalpha build canonical
vnalpha build features --date <date>
vnalpha score --date <date>
vnalpha watchlist --date <date>
```

The remaining R0 work is validation hardening.

### Required additions

Add a verification target:

```text
make verify-r0
```

It should run:

```text
cd vnalpha && pytest -q \
  tests/test_phase5_e2e.py \
  tests/test_features.py \
  tests/test_warehouse.py \
  tests/test_command_warehouse.py
```

If CLI-level smoke can run without provider data, add:

```text
vnalpha init
vnalpha build canonical
vnalpha build features --date <fixture-date>
vnalpha score --date <fixture-date>
vnalpha watchlist --date <fixture-date>
```

For provider-backed data, keep it in manual/deployed-host validation, not normal CI.

### Required test cases

- Existing warehouse missing new feature metadata columns upgrades safely.
- Existing warehouse missing chat/outcome columns upgrades safely.
- Feature status is `MISSING_BENCHMARK` when VNINDEX is absent.
- Feature status is `STALE_DATE` when actual bar date is older than target date.
- Feature status is `EXACT_DATE` when target date has an exact bar.
- Unknown universe returns non-zero at CLI boundary.
- Explicit symbols override named universe at CLI boundary.

## R1 design

R1 is about alignment between architecture and reality. It should not add runtime features.

Add or update:

```text
vnalpha/docs/11-deployment-architecture.md
vnalpha/docs/12-operator-runbook.md
vnalpha/docs/13-r0-r4-completion-matrix.md
```

The completion matrix should include:

```text
phase
completion estimate
blocking gaps
implemented evidence
unit/integration evidence
runtime evidence
docs evidence
remaining deferred work
```

Documentation must explicitly map:

```text
docker-compose.yml
vnalpha/Dockerfile
packaging/scripts/openstock-verify
packaging/scripts/openstock-backup-warehouse
packaging/scripts/openstock-run-pipeline if added
packaging/systemd/openstock-data-platform.service
packaging/systemd/openstock-daily-pipeline.service
packaging/systemd/openstock-daily-pipeline.timer
package build files and launcher paths
warehouse path
config env paths
```

## R2 design

### Pipeline wrapper

The daily pipeline must be controlled by one wrapper that holds a lock for the full pipeline duration.

Add:

```text
packaging/scripts/openstock-run-pipeline
```

Expected behavior:

```text
openstock-run-pipeline [--date YYYY-MM-DD] [--start YYYY-MM-DD] [--ci-fixture] [--dry-run]
```

The wrapper should:

1. source `/etc/openstock/openstock.env` when present;
2. create required directories;
3. acquire a lock with `flock` for the whole run;
4. run the pipeline in the correct order;
5. use `sync index --symbol VNINDEX` for benchmark data;
6. fail on the first required command failure;
7. print structured `[OK]`, `[WARN]`, `[FAIL]`, and `[INFO]` lines;
8. release the lock reliably.

The systemd service should call the wrapper once, not run multiple independent `ExecStart=` commands.

### Correct pipeline order

```text
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start <start>
vnalpha sync index --symbol VNINDEX --start <start>
vnalpha build canonical
vnalpha build features --date <date>
vnalpha score --date <date>
vnalpha watchlist --date <date>
```

When running inside Docker Compose:

```text
docker compose run --rm vnalpha-worker <command>
```

### Static CI verification

`openstock-verify --ci` should validate static properties without requiring live provider data:

```text
bash -n packaging/scripts/openstock-verify
bash -n packaging/scripts/openstock-backup-warehouse
bash -n packaging/scripts/openstock-run-pipeline
systemd-analyze verify packaging/systemd/*.service packaging/systemd/*.timer when available
docker compose config
confirm vnstock-service binds to 127.0.0.1:6900
confirm vnalpha-worker is profile-gated
confirm worker env contains VNSTOCK_SERVICE_URL and VNALPHA_WAREHOUSE_PATH
confirm forbidden endpoint list exists in vnstock service code
confirm package metadata/launcher files exist
confirm no TUI daemon is configured
```

### Deployed-host verification

Default `openstock-verify` should remain stricter and check running services:

```text
docker available
compose available
vnstock-service running
/healthz returns 200
restricted HTTP paths return 404
warehouse directory/file/schema exist
vnalpha --help works
vnalpha tui --help or import check works
watchlist command returns success or explicit no-data warning
assistant config absence is warning/skip, not failure
```

### Package proof

Add a build/install proof path:

```text
make build-vnalpha-deb
make verify-vnalpha-deb
```

`verify-vnalpha-deb` should verify at minimum:

```text
package artifact exists
control metadata exists
/usr/bin/vnalpha launcher exists in package tree or installed package
/usr/bin/vnalpha-poc launcher exists in package tree or installed package
/etc/vnalpha/vnalpha.env exists in package tree or installed package
package install does not remove /var/lib/openstock/warehouse
vnalpha --help works after install in supported environment
```

## R3 design

R3 needs stronger TUI evidence.

Add TUI pilot tests using Textual's testing support where possible. Tests should be skipped only when Textual is unavailable; they should not silently pass as placeholders.

Required pilot checks:

```text
app mounts
home screen is initial
switch to watchlist
switch to commands
switch to assistant
switch to rejected
switch to quality
switch to outcomes
ChatPanel remains mounted after each switch
cancel plan action calls ChatController cancel path
approve plan action calls ChatController approve path
empty warehouse surfaces show messages instead of crashing
```

If full pilot tests are unstable, add a non-interactive smoke command:

```text
vnalpha tui --smoke --date <date>
```

The smoke command may instantiate the app and verify imports/composition without running an interactive loop.

## R4 design

### Controller ownership

ChatController must own all chat orchestration.

ChatPanel should become a view/controller adapter:

```text
ChatPanel.on_input_submitted(raw)
  -> self._chat_controller.handle_turn(raw)

ChatPanel.action_approve_plan()
  -> self._chat_controller.approve_pending_plan()

ChatPanel.action_cancel_plan()
  -> self._chat_controller.cancel_pending_plan()
```

Remove or stop using ChatPanel-local paths:

```text
_VALID_COMMANDS
_get_command_registry
_parse_command
_dispatch_command_sync
_dispatch_assistant
_run_ask
self._registry.execute(...)
direct AssistantApp construction from ChatPanel
```

It is acceptable to keep small rendering helpers in ChatPanel, but not business orchestration.

### Chat session lifecycle

On TUI ChatPanel mount:

1. open short-lived connection;
2. run migrations;
3. create or resume a chat_session for target date and surface;
4. construct ChatController with that chat_session_id;
5. close setup connection.

### Persistence semantics

Every turn should create audit rows:

```text
user prompt                         chat_message(role='user')
assistant answer                    chat_message(role='assistant')
assistant refusal                   chat_message(role='assistant', message_type='refusal')
slash command input                 chat_message(role='user', message_type='slash_command')
slash command result                chat_message(role='assistant', research_session_id=...)
chat-local command input            chat_message(role='user', message_type='chat_local_command')
chat-local command result           chat_message(role='system' or 'assistant')
plan preview                        chat_message(role='assistant', message_type='plan_preview', plan_json=...)
plan approval                       chat_message(role='user', message_type='plan_approval')
plan cancellation                   chat_message(role='user' or 'system', message_type='plan_cancel')
trace event                         chat_message(role='trace', message_type='tool_trace_event')
```

### Clear semantics

`/clear` should clear the visible UI log but preserve persisted transcript.

If destructive deletion is kept, it must require an explicit command such as:

```text
/clear --forget
```

Preferred schema change:

```text
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT TRUE
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ
```

Then:

```text
/clear          -> mark current session messages is_visible=false, keep rows
/clear --forget -> delete only after explicit destructive flag, if product owner accepts this behavior
```

### Permission evaluation before pending plan

Before a plan becomes pending, every planned tool must be classified:

```text
ALLOW       safe read-only; may auto-run in auto mode
ASK         may become pending and needs approval
DENY        refused in current mode
HARD_DENY   refused permanently, never pending, never approvable
```

Any restricted plan step must result in a refusal message and persisted audit row. It must not be stored in `_pending_plan`.

### Trace persistence

The trace callback used by ChatController should both render and persist trace events when a chat session is active.

`/trace` should read from persisted trace messages linked to the current chat session.

## Validation report

Add:

```text
vnalpha/docs/13-r0-r4-completion-matrix.md
vnalpha/docs/14-r0-r4-validation-report.md
```

The validation report should include exact command output summaries for:

```text
make test-vnalpha
make lint-vnalpha
make verify-r0
make verify-r2-ci
docker compose config
openstock-verify --ci
openstock-run-pipeline --dry-run or --ci-fixture
manual deployed-host openstock-verify
manual openstock-backup-warehouse
TUI manual smoke
ChatPanel manual smoke
```

If a command cannot be run in the current environment, record it as `NOT RUN` and explain why. Do not convert `NOT RUN` to pass.
