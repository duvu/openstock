# Tasks: Complete R0-R4 Terminal POC

## 0. Completion governance

- [x] 0.1 Treat this change as the authoritative R0-R4 completion gate.
- [x] 0.2 Reconcile earlier checked OpenSpec tasks with actual implementation evidence.
- [x] 0.3 Do not mark any task complete unless backed by working code, an automated test, a runnable script, or a concrete manual smoke command.
- [x] 0.4 Add an implementation status note listing completed, deferred, and explicitly out-of-scope items.
- [x] 0.5 Confirm no R0-R4 work depends on the R5 local runtime/server.

## 1. R0 — POC baseline stabilization

### 1.1 CLI and command contract

- [x] 1.1.1 Verify `vnalpha init` initializes a fresh DuckDB warehouse.
- [x] 1.1.2 Verify `vnalpha sync symbols` populates `symbol_master` or returns explicit skipped/error counts.
- [x] 1.1.3 Verify `vnalpha sync ohlcv --universe VN30 --start <date>` works or fails with actionable error output.
- [x] 1.1.4 Verify `vnalpha sync ohlcv --symbols FPT,VNM --start <date>` works and overrides `--universe`.
- [x] 1.1.5 Verify unknown universe names fail closed with clear messages.
- [x] 1.1.6 Verify `vnalpha sync index --symbol VNINDEX --start <date>` stores benchmark data.
- [x] 1.1.7 Verify `vnalpha build canonical` builds canonical OHLCV.
- [x] 1.1.8 Verify `vnalpha build features --date <date>` creates feature snapshots.
- [x] 1.1.9 Verify `vnalpha score --date <date>` persists candidate scores and daily watchlist rows.
- [x] 1.1.10 Verify `vnalpha watchlist --date <date>` shows useful rows or a clear no-data message.
- [x] 1.1.11 Align `Makefile` targets with the actual CLI contract.

### 1.2 Warehouse migrations

- [x] 1.2.1 Ensure migrations create all R0-R4 tables on a fresh warehouse.
- [x] 1.2.2 Ensure migrations safely upgrade existing DuckDB files with `ADD COLUMN IF NOT EXISTS` where needed.
- [x] 1.2.3 Add or verify migration tests for existing/minimal warehouse upgrade.
- [x] 1.2.4 Ensure migration logs are actionable when a schema operation fails.

### 1.3 Canonical OHLCV and data quality

- [x] 1.3.1 Verify canonical builder enforces one row per `(symbol, time, interval)`.
- [x] 1.3.2 Verify canonical builder preserves selected provider, source run, and quality status.
- [x] 1.3.3 Validate or reject invalid rows: missing close, high lower than low, negative price, negative volume.
- [x] 1.3.4 Persist severe data-quality failures to `rejected_symbol` or propagate `POOR_DATA_QUALITY` risk flags.
- [x] 1.3.5 Add tests for pass/warn/fail data-quality cases.

### 1.4 Feature store

- [x] 1.4.1 Verify feature builder computes trend features.
- [x] 1.4.2 Verify feature builder computes volume/liquidity features.
- [x] 1.4.3 Verify feature builder computes volatility features.
- [x] 1.4.4 Verify feature builder computes base/range/proximity features.
- [x] 1.4.5 Verify feature builder computes relative strength versus VNINDEX when benchmark exists.
- [x] 1.4.6 Verify missing benchmark produces `MISSING_BENCHMARK`, not silent degradation.
- [x] 1.4.7 Verify stale date produces `STALE_DATE` with actual `as_of_bar_date`.
- [x] 1.4.8 Verify exact date produces `EXACT_DATE`.
- [x] 1.4.9 Verify insufficient history is counted and traceable.
- [x] 1.4.10 Add feature tests for benchmark and insufficient-history scenarios.

### 1.5 Scoring and watchlist

- [x] 1.5.1 Verify scoring reads only persisted `feature_snapshot` rows.
- [x] 1.5.2 Verify scoring persists `candidate_score` rows with evidence, risk flags, and lineage.
- [x] 1.5.3 Verify `daily_watchlist` is derived from persisted `candidate_score`, not transient in-memory scores.
- [x] 1.5.4 Verify `IGNORE` candidates are excluded from the watchlist.
- [x] 1.5.5 Enforce canonical `candidate_class` values before persistence.
- [x] 1.5.6 Enforce canonical `setup_type` values before persistence.
- [x] 1.5.7 Add tests that legacy aliases cannot be persisted as final Phase 5 values.
- [x] 1.5.8 Align score scale in code, docs, CLI output, and tests.

### 1.6 Rich watchlist and query surface

- [x] 1.6.1 Verify rich watchlist query includes rank, symbol, score, candidate class, setup type, evidence, risk flags, lineage, and data-quality status.
- [x] 1.6.2 Verify CLI watchlist renders a useful subset and points to TUI/detail for full evidence.
- [x] 1.6.3 Verify detail query can show score breakdown and lineage for a selected symbol/date.
- [x] 1.6.4 Add tests for rich watchlist query shape and JSON decoding.

### 1.7 Fixture-backed E2E

- [x] 1.7.1 Keep fixture E2E fully offline.
- [x] 1.7.2 Include VNINDEX benchmark fixture.
- [x] 1.7.3 Include at least one strong candidate fixture.
- [x] 1.7.4 Include at least one weak or ignored candidate fixture.
- [x] 1.7.5 Include at least one insufficient-history or poor-quality candidate fixture.
- [x] 1.7.6 Assert `feature_snapshot` rows exist.
- [x] 1.7.7 Assert `candidate_score` rows exist.
- [x] 1.7.8 Assert `daily_watchlist` rows exist or explicit no-data behavior is expected.
- [x] 1.7.9 Assert at least one non-`IGNORE` candidate exists in candidate scores.
- [x] 1.7.10 Assert poor-quality or insufficient-history symbols are skipped, rejected, or risk-flagged.

## 2. R1 — POC deployment architecture

- [x] 2.1 Verify `vnalpha/docs/11-deployment-architecture.md` matches actual repo files and commands.
- [x] 2.2 Document final component responsibilities for `vnstock-service`, `vnalpha-worker`, DuckDB, and host-native `vnalpha`.
- [x] 2.3 Document canonical warehouse path `/var/lib/openstock/warehouse/warehouse.duckdb`.
- [x] 2.4 Document config paths and environment variables.
- [x] 2.5 Document DuckDB concurrency rules and writer restrictions.
- [x] 2.6 Document research-only safety boundary.
- [x] 2.7 Document known limitations and deferred R5+ work.
- [x] 2.8 Add an operator runbook with exact install/start/sync/verify/backup/rollback commands.
- [x] 2.9 Ensure all architecture docs distinguish implemented behavior from planned behavior.

## 3. R2 — Deploy and verify POC

### 3.1 Docker data platform

- [x] 3.1.1 Verify top-level `docker-compose.yml` starts `vnstock-service` only by default.
- [x] 3.1.2 Verify `vnstock-service` binds to `127.0.0.1:6900` by default.
- [x] 3.1.3 Verify healthcheck calls `/healthz`.
- [x] 3.1.4 Verify persistent vnstock config mount exists.
- [x] 3.1.5 Verify `vnalpha-worker` is profile-gated and does not run by default.
- [x] 3.1.6 Verify `vnalpha-worker` uses shared warehouse mount.
- [x] 3.1.7 Verify `VNSTOCK_SERVICE_URL=http://vnstock-service:6900` inside worker.
- [x] 3.1.8 Verify `VNALPHA_WAREHOUSE_PATH=/warehouse/warehouse.duckdb` inside worker.
- [x] 3.1.9 Add `docker compose config` validation to CI or documented smoke checklist.

### 3.2 Worker image

- [x] 3.2.1 Verify `vnalpha/Dockerfile` builds a worker image.
- [x] 3.2.2 Verify worker image can run `vnalpha --help`.
- [x] 3.2.3 Verify worker image can run `init` against mounted warehouse.
- [x] 3.2.4 Verify worker image can run CI-safe smoke pipeline when fixture mode is enabled or documented.
- [x] 3.2.5 Ensure worker runs as non-root where practical.

### 3.3 Debian package

- [x] 3.3.1 Add or verify packaging script for `vnalpha.deb`.
- [x] 3.3.2 Package Python virtual environment under `/opt/vnalpha/venv`.
- [x] 3.3.3 Install `/usr/bin/vnalpha` launcher.
- [x] 3.3.4 Install `/usr/bin/vnalpha-poc` launcher.
- [x] 3.3.5 Install `/etc/vnalpha/vnalpha.env` as an operator-editable config file.
- [x] 3.3.6 Ensure package install/upgrade does not delete `/var/lib/openstock/warehouse`.
- [x] 3.3.7 Verify `vnalpha --help` works after package install.
- [x] 3.3.8 Verify `vnalpha tui --date <demo-date>` starts from host terminal or passes non-interactive entrypoint check.

### 3.4 systemd and scheduler

- [x] 3.4.1 Add or verify `openstock-data-platform.service`.
- [x] 3.4.2 Ensure service creates `/var/lib/openstock/warehouse` before startup.
- [x] 3.4.3 Ensure service creates `/var/lib/openstock/vnstock-config` before startup.
- [x] 3.4.4 Ensure service starts only long-running data services.
- [x] 3.4.5 Add optional `openstock-daily-pipeline.service`.
- [x] 3.4.6 Add optional `openstock-daily-pipeline.timer`.
- [x] 3.4.7 Ensure scheduled pipeline uses worker jobs, not TUI.
- [x] 3.4.8 Add writer lock to scheduled pipeline.

### 3.5 Verification command

- [x] 3.5.1 Add `openstock-verify`.
- [x] 3.5.2 Add `openstock-verify --ci` mode.
- [x] 3.5.3 Check Docker availability.
- [x] 3.5.4 Check Docker Compose availability.
- [x] 3.5.5 Check data platform status when systemd is available.
- [x] 3.5.6 Check `vnstock-service` container status.
- [x] 3.5.7 Check `GET /healthz` returns ok.
- [x] 3.5.8 Check forbidden endpoints return not found: `/v1/order`, `/v1/account`, `/v1/portfolio`, `/v1/trading`.
- [x] 3.5.9 Check warehouse directory exists.
- [x] 3.5.10 Check warehouse schema initializes or already exists.
- [x] 3.5.11 Check `vnalpha --help`.
- [x] 3.5.12 Check `vnalpha watchlist --date <demo-date>` behavior.
- [x] 3.5.13 Check TUI import/entrypoint without launching fully interactive UI in CI mode.
- [x] 3.5.14 Warn, not fail, when optional LLM env is absent.
- [x] 3.5.15 Print `[OK]`, `[WARN]`, and `[FAIL]` status lines.
- [x] 3.5.16 Return non-zero when required checks fail.

### 3.6 Backup and rollback

- [x] 3.6.1 Add `openstock-backup-warehouse`.
- [x] 3.6.2 Store backups under `/var/lib/openstock/warehouse/backups`.
- [x] 3.6.3 Use timestamped backup names.
- [x] 3.6.4 Refuse unsafe backup when writer lock exists unless explicit force flag is used.
- [x] 3.6.5 Document rollback of `vnalpha.deb`.
- [x] 3.6.6 Document rollback of Docker images/data platform.
- [x] 3.6.7 Document guarded DuckDB restore.
- [x] 3.6.8 Require `openstock-verify` after restore.

## 4. R3 — Terminal Workspace POC

### 4.1 TUI shell and screens

- [x] 4.1.1 Ensure `vnalpha tui --date <demo-date>` starts reliably.
- [x] 4.1.2 Implement persistent workspace shell with main workspace area and persistent ChatPanel.
- [x] 4.1.3 Wire watchlist screen to DuckDB query service.
- [x] 4.1.4 Wire symbol detail screen to selected symbol/date query service.
- [x] 4.1.5 Wire quality screen to data-quality and feature status query service.
- [x] 4.1.6 Wire rejected symbols screen to `rejected_symbol` query service.
- [x] 4.1.7 Wire outcomes/calibration screen to outcome tables.
- [x] 4.1.8 Add explicit empty states for missing warehouse, no watchlist, no detail, no rejected data, and no outcomes.
- [x] 4.1.9 Ensure TUI does not require Docker interactive execution.

### 4.2 Navigation and UX

- [x] 4.2.1 Add or verify keyboard shortcuts for home, watchlist, command/help, assistant/chat, rejected, quality, outcomes, quit.
- [x] 4.2.2 Ensure watchlist can open symbol detail.
- [x] 4.2.3 Ensure selected symbol/date context can be passed to ChatPanel.
- [x] 4.2.4 Add command palette or slash command help surface.
- [x] 4.2.5 Add read-only demo mode.
- [x] 4.2.6 Add status/trace area or integrate trace events into ChatPanel.

### 4.3 TUI tests

- [x] 4.3.1 Add TUI app construction smoke test.
- [x] 4.3.2 Add screen import tests.
- [x] 4.3.3 Add navigation action smoke tests.
- [x] 4.3.4 Add ChatPanel construction smoke test.
- [x] 4.3.5 Add non-interactive TUI entrypoint check for CI.

## 5. R4 — OpenCode-style Chat Workspace Completion

### 5.1 Chat session lifecycle

- [x] 5.1.1 Create or resume `chat_session` when TUI starts.
- [x] 5.1.2 Persist every user turn to `chat_message`.
- [x] 5.1.3 Persist every assistant response/refusal to `chat_message`.
- [x] 5.1.4 Persist slash command outputs as `chat_message` rows or linked `research_session` rows.
- [x] 5.1.5 Link assistant turns to `assistant_session`.
- [x] 5.1.6 Link command turns to `research_session`.
- [x] 5.1.7 Link tool traces through `tool_trace_ids_json` where applicable.
- [x] 5.1.8 Implement `/new` to start a fresh chat session.
- [x] 5.1.9 Implement `/clear` to clear visible transcript without deleting persisted audit history unless explicitly designed otherwise.

### 5.2 Unified command execution

- [x] 5.2.1 Remove ChatPanel-only command dispatch paths that bypass shared execution.
- [x] 5.2.2 Use shared parser, command registry, permission evaluator, and traced tool executor.
- [x] 5.2.3 Ensure CLI `vnalpha cmd`, TUI command screen, ChatPanel slash commands, and assistant tool calls share execution semantics.
- [x] 5.2.4 Persist command execution traces.
- [x] 5.2.5 Add tests proving ChatPanel slash commands use the shared execution path.

### 5.3 Deterministic multi-turn context

- [x] 5.3.1 Track target date.
- [x] 5.3.2 Track selected symbol.
- [x] 5.3.3 Track last command.
- [x] 5.3.4 Track last compared symbols.
- [x] 5.3.5 Track last plan.
- [x] 5.3.6 Track last tool traces.
- [x] 5.3.7 Implement `/context` to show current deterministic context.
- [x] 5.3.8 Ensure context is derived from persisted state and visible UI state, not hidden LLM memory.

### 5.4 Plan preview and approval

- [x] 5.4.1 Implement plan preview for pipeline/admin actions.
- [x] 5.4.2 Implement explicit approve action.
- [x] 5.4.3 Implement explicit cancel action.
- [x] 5.4.4 Implement `/plan` to show pending or last plan.
- [x] 5.4.5 Ensure read-only commands do not require approval.
- [x] 5.4.6 Ensure pipeline/write/admin actions require approval.
- [x] 5.4.7 Persist plan JSON and approval/cancel decision.
- [x] 5.4.8 Add tests for preview/approve/cancel.

### 5.5 Trace timeline

- [x] 5.5.1 Render tool start/success/failure events in ChatPanel.
- [x] 5.5.2 Implement `/trace` to show recent traces for the current chat/session/context.
- [x] 5.5.3 Persist trace correlation IDs.
- [x] 5.5.4 Ensure failed tools show actionable error summaries.
- [x] 5.5.5 Add tests for trace rendering or trace result formatting.

### 5.6 Chat-local commands

- [x] 5.6.1 Implement `/help` for chat-local and research slash commands.
- [x] 5.6.2 Implement `/new`.
- [x] 5.6.3 Implement `/clear`.
- [x] 5.6.4 Implement `/context`.
- [x] 5.6.5 Implement `/plan`.
- [x] 5.6.6 Implement `/trace`.
- [x] 5.6.7 Ensure unknown chat commands fail closed with useful help.

### 5.7 Research-only hard-deny

- [x] 5.7.1 Add or verify permission states: `allow`, `ask`, `deny`, `hard_deny`.
- [x] 5.7.2 Hard-deny broker order.
- [x] 5.7.3 Hard-deny account access.
- [x] 5.7.4 Hard-deny portfolio mutation.
- [x] 5.7.5 Hard-deny margin.
- [x] 5.7.6 Hard-deny transfer.
- [x] 5.7.7 Hard-deny trading.
- [x] 5.7.8 Hard-deny automated execution.
- [x] 5.7.9 Hard-deny arbitrary shell.
- [x] 5.7.10 Hard-deny raw SQL from prompt.
- [x] 5.7.11 Hard-deny trace hiding and safety bypass.
- [x] 5.7.12 Add tests that prompt text cannot bypass hard-deny rules.

## 6. Final validation

- [x] 6.1 `make install-vnalpha` passes.
- [x] 6.2 `make lint-vnalpha` passes or documented exceptions are explicit.
- [x] 6.3 `make test-vnalpha` passes.
- [x] 6.4 `docker compose config` passes from repo root.
- [x] 6.5 `docker compose up -d vnstock-service` starts service localhost-only.
- [x] 6.6 `docker compose --profile job run --rm vnalpha-worker init` succeeds.
- [x] 6.7 Worker smoke pipeline succeeds or documented fixture-equivalent succeeds.
- [x] 6.8 `vnalpha.deb` builds.
- [x] 6.9 `vnalpha.deb` installs and exposes `vnalpha`.
- [x] 6.10 `openstock-verify --ci` passes.
- [x] 6.11 `openstock-verify` passes on local deployed host.
- [x] 6.12 `openstock-backup-warehouse` creates a backup.
- [x] 6.13 Manual TUI smoke confirms watchlist, detail, quality, rejected, outcomes, and ChatPanel are usable.
- [x] 6.14 Manual safety smoke confirms forbidden endpoints and chat hard-deny behavior.
- [x] 6.15 Update OpenSpec task status only after validation evidence exists.
