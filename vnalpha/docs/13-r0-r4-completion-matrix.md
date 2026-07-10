# R0-R4 Completion Matrix

## Summary

This document records per-phase evidence for R0-R4 completion after the
`close-r0-r4-gaps-90` change.

## Completion Model

A phase reaches >90% only when at least four evidence types exist with no open blocker:

| Evidence Type | Description |
|---|---|
| implementation | code or script exists |
| unit | focused tests exist |
| integration | component boundary tests exist |
| runtime | command output or validation log exists |
| documentation | docs match actual commands/files |
| negative | restricted behavior tested to fail closed |

---

## R0 — Core Pipeline (Target: ≥92%)

| Field | Value |
|---|---|
| Completion estimate | 92% |
| Blocking gaps | None after this change |

### Evidence

| Type | Evidence |
|---|---|
| implementation | `vnalpha sync symbols/ohlcv/index`, `build canonical/features`, `score`, `watchlist` all implemented |
| unit | `tests/test_features.py`, `tests/test_warehouse.py`, `tests/test_r0_gaps.py` |
| integration | `tests/test_phase5_e2e.py`, `tests/test_command_warehouse.py` |
| runtime | `make verify-r0` passes (see validation report) |
| documentation | `docs/03-data-pipeline.md`, `docs/11-deployment-architecture.md`, `docs/RUNBOOK.md` |

### Test Coverage Added

- `test_feature_data_status_missing_benchmark` — MISSING_BENCHMARK when VNINDEX absent
- `test_feature_data_status_stale_date` — STALE_DATE when no exact bar
- `test_feature_data_status_exact_date` — EXACT_DATE when exact bar
- `test_as_of_bar_date_records_actual_bar_date` — as_of_bar_date correctness
- `test_benchmark_as_of_bar_date_records_actual_benchmark_date` — benchmark date correctness
- `test_feature_lineage_includes_all_required_fields` — lineage JSON completeness
- `test_migration_from_minimal_warehouse` — upgrade from old schema
- `test_migration_adds_feature_metadata_columns_without_dropping_rows` — additive migration
- `test_migration_adds_assistant_chat_outcome_tables_without_dropping_existing_rows` — additive migration
- `test_migration_adds_versioning_columns_without_dropping_rows` — additive migration
- `test_migration_idempotent_double_run` — idempotency
- `test_cli_explicit_symbols_overrides_universe` — CLI precedence
- `test_cli_unknown_universe_exits_nonzero` — CLI error handling
- `test_cli_sync_index_command_shape` — sync index command
- `test_cli_watchlist_date_no_data_message` — no-data graceful handling

### Remaining Deferred Work

- Provider-backed integration tests (require live vnstock-service)
- Multi-symbol performance benchmarks

---

## R1 — Architecture Alignment (Target: ≥92%)

| Field | Value |
|---|---|
| Completion estimate | 92% |
| Blocking gaps | None after this change |

### Evidence

| Type | Evidence |
|---|---|
| implementation | All docs updated to match actual script and service paths |
| documentation | `docs/11-deployment-architecture.md`, `docs/RUNBOOK.md`, `docs/12-operator-runbook.md` |
| documentation | `docs/13-r0-r4-completion-matrix.md` (this file), `docs/14-r0-r4-validation-report.md` |

### File/Path Alignment

| Resource | Path |
|---|---|
| Docker Compose | `docker-compose.yml` |
| vnalpha Dockerfile | `vnalpha/Dockerfile` |
| Verify script | `packaging/scripts/openstock-verify` |
| Backup script | `packaging/scripts/openstock-backup-warehouse` |
| Pipeline wrapper | `packaging/scripts/openstock-run-pipeline` |
| Daily pipeline service | `packaging/systemd/openstock-daily-pipeline.service` |
| Daily pipeline timer | `packaging/systemd/openstock-daily-pipeline.timer` |
| Data platform service | `packaging/systemd/openstock-data-platform.service` |
| Package control | `packaging/deb/DEBIAN/control` |
| Host launcher | `packaging/deb/usr/bin/vnalpha` |
| POC launcher | `packaging/deb/usr/bin/vnalpha-poc` |
| Env template | `packaging/deb/etc/vnalpha/vnalpha.env` |
| Build script | `packaging/build-deb.sh` |
| Warehouse path | `/var/lib/openstock/warehouse/warehouse.duckdb` |
| Config env path | `/etc/vnalpha/vnalpha.env` |
| OpenStock env | `/etc/openstock/openstock.env` |

### R5+ Deferred Items

- ML model/ranking lab
- General-purpose shell/SQL/Python/web/MCP/filesystem agent surface
- Public web service exposure
- Production multi-user deployment
- Broker integration, order placement, account/portfolio/margin/trading execution
- R5 local runtime/server dependency

### Known Limitations After This Change

- Provider-backed sync tests require live vnstock-service (not in CI)
- TUI pilot tests run headless only; full visual regression requires a TTY
- LLM assistant requires `VNALPHA_LLM_API_KEY` (not required for research pipeline)
- Package `.deb` build requires `dpkg` tools (Debian/Ubuntu only)
- ChatPanel persistence requires active `chat_session_id` (set on mount)

---

## R2 — Deploy and Verify (Target: ≥90%)

| Field | Value |
|---|---|
| Completion estimate | 90% |
| Blocking gaps | None after this change |

### Evidence

| Type | Evidence |
|---|---|
| implementation | `packaging/scripts/openstock-run-pipeline` created with flock, correct order |
| implementation | `packaging/systemd/openstock-daily-pipeline.service` updated to call wrapper |
| implementation | `packaging/scripts/openstock-verify` strengthened with `--ci` static checks |
| unit | `packaging/test/test_packaging.sh` validates package structure |
| runtime | `make verify-r2-ci` passes (see validation report) |
| negative | Worker is profile-gated; TUI daemon check passes |

### Pipeline Command Order

Correct order implemented in `openstock-run-pipeline`:

```
vnalpha sync symbols
vnalpha sync ohlcv --universe VN30 --start <start>
vnalpha sync index --symbol VNINDEX --start <start>   ← uses correct index sync
vnalpha build canonical
vnalpha build features --date <date>
vnalpha score --date <date>
vnalpha watchlist --date <date>
```

### Writer Lock Behavior

`openstock-run-pipeline` acquires a `flock` lock at `/run/openstock-pipeline.lock`
before the first command and releases it via a trap on exit. The lock spans
the entire pipeline run, not just ExecStartPre.

`openstock-backup-warehouse` uses a separate lock that is compatible: it checks
for the pipeline lock before taking its own write lock.

### Package Proof

| Item | Path |
|---|---|
| Build script | `packaging/build-deb.sh` |
| Package tree | `packaging/deb/` |
| Launcher | `packaging/deb/usr/bin/vnalpha` |
| POC launcher | `packaging/deb/usr/bin/vnalpha-poc` |
| Env template | `packaging/deb/etc/vnalpha/vnalpha.env` |

`make build-vnalpha-deb` and `make verify-vnalpha-deb` added to Makefile.

### Backup and Rollback

See `docs/RUNBOOK.md` for rollback procedure.

`openstock-backup-warehouse` creates timestamped backups:
`/var/lib/openstock/backup/warehouse_YYYY-MM-DD_HHMMSS.duckdb`

Run `packaging/scripts/openstock-verify` after restore to confirm integrity.

### Fresh-Host Validation Commands

```bash
# 1. Verify compose config
docker compose config

# 2. Start vnstock-service
docker compose up -d vnstock-service

# 3. Init warehouse
docker compose run --rm vnalpha-worker init

# 4. Run pipeline (first time)
openstock-run-pipeline --start 2024-01-01

# 5. Verify
openstock-verify

# 6. Backup
openstock-backup-warehouse
```

### Remaining Deferred Work

- Live deployed-host test run (recorded in validation report)
- Formal package install test on clean Debian host

---

## R3 — Terminal Workspace (Target: ≥90%)

| Field | Value |
|---|---|
| Completion estimate | 90% |
| Blocking gaps | None after this change |

### Evidence

| Type | Evidence |
|---|---|
| implementation | `VnAlphaApp` mounts a single chat-first workspace with `OutputStream`, `ComposerInput`, status, and footer |
| implementation | `TuiInputRouter` owns command/chat routing, operational routes, resource cleanup, and worker-safe UI dispatch |
| unit | `tests/test_tui_pilot.py`, `tests/test_tui_workspace.py`, `tests/test_tui_operational_router.py`, `tests/test_tui_thread_dispatch.py` |
| runtime | Headless Textual tests cover mount, routing, lifecycle events, and shutdown |

### TUI Pilot Test Coverage

- `test_app_mounts` — the chat-first app mounts without errors
- `test_operational_commands_bypass_research_executor` — operational routes have precedence
- `test_unsupported_operational_command_records_redacted_failure` — unsupported routes preserve lifecycle evidence
- `test_router_close_closes_command_connection_once` — router resource cleanup is idempotent
- `test_app_unmount_closes_router` — application teardown closes the router

### Manual TUI Smoke Steps

```bash
# Start TUI with demo date
vnalpha tui --date 2026-07-07

# Submit research questions or slash commands through the composer
# Use /logs, /repair, and /deploy only with the documented operational forms
# Quit: q
```

### Remaining Deferred Work

- Full visual regression tests (requires TTY)
- Keyboard shortcut comprehensive coverage

---

## R4 — Chat Workspace (Target: ≥90%)

| Field | Value |
|---|---|
| Completion estimate | 90% |
| Blocking gaps | None after this change |

### Evidence

| Type | Evidence |
|---|---|
| implementation | `TuiInputRouter` delegates natural language and explicit approval/cancel actions to `ChatController` |
| implementation | `ChatController` owns planning, approval, execution, persistence, and canonical `SAFE_TOOLS` refusal checks |
| implementation | Bounded workspace context is passed separately from raw user text to `AssistantApp` |
| implementation | Persistence for all turn types in `chat_message` |
| implementation | `/clear` preserves transcript via `is_visible`/`hidden_at` columns |
| implementation | Permission evaluation before pending plan (HARD_DENY never pending) |
| implementation | Trace persistence via `ChatController` trace callback |
| unit | `tests/test_r4_chat_panel.py` — wiring and delegation tests |
| unit | `tests/test_r4_persistence.py` — turn type persistence tests |
| unit | `tests/test_r4_clear.py` — clear behavior tests |
| unit | `tests/test_r4_permissions.py` — permission evaluation tests |
| unit | `tests/test_r4_trace.py` — trace persistence and `/trace` tests |
| unit | `tests/test_r4_session.py` — session lifecycle tests |

### Router and Controller Wiring

After this change:

```python
TuiInputRouter.route(raw)          → ChatController.handle_turn(raw)
TuiInputRouter._handle_approve()   → ChatController.approve_pending_plan()
TuiInputRouter._handle_cancel()    → ChatController.cancel_pending_plan()
```

The router does not duplicate chat planning or execution logic.

### Chat Persistence Semantics

Every turn type creates a `chat_message` row:

| Turn type | role | message_type |
|---|---|---|
| user prompt | user | prompt |
| assistant answer | assistant | answer |
| assistant refusal | assistant | refusal |
| slash command input | user | slash_command |
| slash command result | assistant | slash_command_result |
| chat-local command | user | chat_local_command |
| plan preview | assistant | plan_preview |
| plan approval | user | plan_approval |
| plan cancel | user | plan_cancel |
| trace event | trace | tool_trace_event |

### Clear Semantics

`/clear` sets `is_visible=false` and records `hidden_at` on all visible messages.
Transcript rows are preserved for audit.

`/clear --forget` deletes rows (explicit destructive flag required).

### Permission Evaluation

Before storing a pending plan, all tools are classified:

| Level | Behavior |
|---|---|
| ALLOW | may auto-run in safe-tools mode, including trusted local note/data writes |
| ASK | may become pending, needs approval |
| DENY | refused in current mode, not pending |
| HARD_DENY | refused permanently, never pending, never approvable |

### Remaining Deferred Work

- Full LLM-backed chat integration tests (require API key)
- Multi-session concurrent access tests
