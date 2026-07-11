# Review: remaining R0-R4 gaps

## Review method

This review treats current repository files as the source of truth. OpenSpec checkboxes and PR descriptions are not counted as completion evidence unless backed by code, tests, runnable scripts, or validation logs.

Files reviewed include the CLI, universe resolver, feature builder, canonical builder, warehouse schema/migrations/repositories, chat repository, ChatController, chat modes, chat safety helpers, TUI app, ChatPanel, outcome screen, E2E tests, TUI/chat tests, Docker Compose, worker Dockerfile, deploy scripts, systemd units, and Makefile.

## Phase status summary

```text
R0 — Core pipeline:              85-90%
R1 — Architecture alignment:     80-85%
R2 — Deploy & verify:            65-75%
R3 — Terminal workspace:         70-80%
R4 — Chat workspace:             50-60% end-to-end
```

Target after this gap-closure change is implemented and validated:

```text
R0 >= 92%
R1 >= 92%
R2 >= 90%
R3 >= 90%
R4 >= 90%
```

## R0 findings

### Already materially closed

- CLI command contract exists for init, sync, build, features, score, watchlist, TUI, command runner, assistant runner, and outcome commands.
- `sync ohlcv` supports explicit symbols, named universe, and fail-closed unknown universe behavior.
- Static VN30 resolver exists.
- Offline fixture E2E pipeline exists.
- Canonical OHLCV deduplication exists.
- Data-quality rejection exists for severe OHLCV defects.
- Feature snapshot metadata exists for actual bar date, benchmark bar date, row counts, status, build version, generated time, and lineage.
- Candidate scoring persistence enforces canonical candidate class and setup type.
- Rich watchlist query exists.

### Remaining R0 gaps

- Add direct tests for `MISSING_BENCHMARK`, `STALE_DATE`, and `EXACT_DATE` feature status.
- Add migration-upgrade tests for older DuckDB files missing newer columns.
- Add a CLI-level pipeline smoke path, not only direct Python function calls.
- Add Makefile target for R0 verification.

## R1 findings

### Already materially closed

- Deployment architecture docs and roadmap exist.
- System shape is coherent: Docker data platform, DuckDB warehouse, host-native terminal workspace.
- Research-only boundary is documented.

### Remaining R1 gaps

- Align docs to actual script paths and service behavior.
- Add phase completion evidence matrix.
- Separate implemented behavior from R5+ deferred runtime/server behavior.
- Document validation logs and residual known limitations.

## R2 findings

### Already materially closed

- Top-level Docker Compose exists with `vnstock-service` and profile-gated `vnalpha-worker`.
- `vnstock-service` binds to localhost by default.
- `vnstock-service` has healthcheck.
- `vnalpha-worker` image exists and uses `vnalpha` entrypoint.
- `openstock-verify` exists.
- `openstock-backup-warehouse` exists.
- systemd data platform wrapper exists.
- systemd daily pipeline timer exists.

### Remaining R2 gaps

- Fix benchmark sync command in the daily pipeline service.
- Replace the current lock approach with a wrapper that protects the whole multi-step pipeline.
- Add `openstock-run-pipeline` or equivalent.
- Add static tests for deploy scripts and systemd files.
- Strengthen `openstock-verify --ci` so it validates static deploy properties instead of skipping too much.
- Prove package build/install and launchers.
- Add a fresh-host validation report or reproducible validation artifact.
- Add Makefile targets for R2 CI and deployed-host verification.

## R3 findings

### Already materially closed

- TUI now uses ContentSwitcher for main workspace.
- Main workspace includes home, watchlist, command, assistant, rejected, quality, and outcomes screens.
- Persistent ChatPanel is composed below the main workspace.
- Key bindings exist for major screens and chat controls.
- Outcome screen has summary and multiple review tables.
- Basic TUI smoke tests exist.

### Remaining R3 gaps

- Add Textual pilot tests that switch screens through the app.
- Verify ChatPanel remains mounted while switching screens.
- Verify watchlist to detail flow.
- Verify empty warehouse behavior across all key surfaces.
- Replace placeholder tests with meaningful assertions.
- Add a non-interactive TUI smoke entrypoint if feasible.

## R4 findings

### Already materially closed

- ChatController exists.
- ChatController classifies slash command, chat-local command, and natural-language input.
- ChatController routes slash commands through CommandExecutor.
- Chat-local commands exist for `/new`, `/clear`, `/context`, `/plan`, `/trace`, and `/help`.
- Execution modes exist for auto safe-read, plan-then-approve, and plan-only.
- Safe read-only tool allowlist exists.
- Permission-state helpers exist.
- Plan approval and cancel tests exist.
- Chat repository helpers exist for chat sessions and messages.

### Remaining R4 gaps

- ChatPanel still owns duplicate command and assistant dispatch paths instead of delegating to ChatController.
- The app approval action expects `panel._chat_controller`, but ChatPanel does not currently create/use that controller.
- Normal user turns, assistant turns, command results, local-command outputs, plan previews, approval/cancel decisions, and trace events are not yet guaranteed to persist as chat messages.
- `/clear` behavior is inconsistent with transcript-preserving audit behavior.
- Restricted planned tools must be refused before pending-plan storage.
- `/trace` must read persisted trace events correlated to the current chat session.
- ChatPanel tests should prove delegation to ChatController, not direct registry dispatch.

## Primary blockers

```text
BLOCKER-1: Wire ChatPanel to ChatController and remove duplicate ChatPanel dispatch paths.
BLOCKER-2: Fix systemd pipeline benchmark sync and writer locking.
BLOCKER-3: Make chat persistence audit-correct for every turn and clear behavior.
BLOCKER-4: Add deploy/fresh-host validation evidence.
BLOCKER-5: Add TUI integration/pilot tests.
```

## Recommended implementation order

1. Fix R4 controller wiring and persistence.
2. Fix R2 pipeline service and writer lock.
3. Strengthen R2 verify/package/fresh-host evidence.
4. Add TUI pilot tests for R3.
5. Add R0/R1 evidence and completion matrix.
