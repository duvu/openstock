# Tasks: Workspace context lifecycle

## 0. Governance

- [x] 0.1 Treat workspace context as curated working memory, not raw transcript dump.
- [x] 0.2 Keep audit logs separate and immutable.
- [x] 0.3 Do not delete audit logs during clean/new lifecycle operations.
- [x] 0.4 Apply redaction/sensitive-content rules before storing workspace text.
- [x] 0.5 Keep fresh warehouse data authoritative over stale workspace summaries.
- [x] 0.6 Do not mark complete without code, tests, and validation evidence.

## 1. Workspace package

- [x] 1.1 Add `vnalpha/src/vnalpha/workspace_context/__init__.py`.
- [x] 1.2 Add `models.py`.
- [x] 1.3 Add `storage.py`.
- [x] 1.4 Add `lifecycle.py`.
- [x] 1.5 Add `compaction.py`.
- [x] 1.6 Add `cleaning.py`.
- [x] 1.7 Add `export.py`.
- [x] 1.8 Add `integration.py`.
- [x] 1.9 Add `observability.py`.

## 2. Workspace models

- [x] 2.1 Define `WorkspaceState`.
- [x] 2.2 Define `WorkspaceArtifactRef`.
- [x] 2.3 Define `WorkspaceInputRef`.
- [x] 2.4 Define `WorkspaceTask`.
- [x] 2.5 Define `WorkspaceStatusReport`.
- [x] 2.6 Define `CompactionResult`.
- [x] 2.7 Define `CleanPlan`.
- [x] 2.8 Define `CleanResult`.
- [x] 2.9 Define `ExportResult`.
- [x] 2.10 Add serialization/deserialization tests.

## 3. Storage

- [x] 3.1 Implement configurable workspace root.
- [x] 3.2 Default root to `.vnalpha/workspaces` or configured data root.
- [x] 3.3 Implement `latest.json` pointer.
- [x] 3.4 Implement `index.json` workspace index.
- [x] 3.5 Implement workspace directory creation.
- [x] 3.6 Implement atomic JSON writes.
- [x] 3.7 Implement JSONL event append.
- [x] 3.8 Implement basic lock file.
- [x] 3.9 Add tests for atomic write and load.

## 4. Workspace lifecycle

- [x] 4.1 Implement `get_or_create_latest_workspace()`.
- [x] 4.2 Implement `create_workspace()`.
- [x] 4.3 Implement `resume_workspace()`.
- [x] 4.4 Implement `list_workspaces()`.
- [x] 4.5 Implement `archive_workspace()`.
- [x] 4.6 Implement `get_status()`.
- [x] 4.7 Implement `record_input()`.
- [x] 4.8 Implement `record_artifact()`.
- [x] 4.9 Implement `record_warning()`.
- [x] 4.10 Implement `record_error()`.
- [x] 4.11 Add lifecycle tests.

## 5. Context files

- [x] 5.1 Generate `workspace.json`.
- [x] 5.2 Generate/update `context.md`.
- [x] 5.3 Generate/update `events.jsonl`.
- [x] 5.4 Create `artifacts/` directory.
- [x] 5.5 Create `archive/` directory.
- [x] 5.6 Create `exports/` directory.
- [x] 5.7 Add tests for file layout.


## 6. Compaction

- [x] 6.1 Implement deterministic compaction from workspace state and curated events.
- [x] 6.2 Include current goal, active symbols/date, findings, assumptions, decisions, open tasks, warnings, and source refs.
- [x] 6.3 Avoid raw audit log ingestion by default.
- [x] 6.4 Write `compact.md`.
- [x] 6.5 Return `CompactionResult`.
- [x] 6.6 Update `last_compacted_at`.
- [x] 6.7 Emit workspace and audit events.
- [x] 6.8 Add compaction tests.

## 7. Cleaning

- [x] 7.1 Implement clean dry-run.
- [x] 7.2 Implement clean plan classification: keep/archive/remove/needs_confirmation.
- [x] 7.3 Implement archive-first cleanup.
- [x] 7.4 Support resolved-errors cleanup.
- [x] 7.5 Support old-events cleanup.
- [x] 7.6 Support artifact cleanup.
- [x] 7.7 Protect audit logs, compact.md, workspace.json, pinned items, and user notes.
- [x] 7.8 Return `CleanResult`.
- [x] 7.9 Add cleaning tests.

## 8. New workspace

- [x] 8.1 Implement `/context new` service behavior.
- [x] 8.2 Compact current workspace by default.
- [x] 8.3 Support `--no-compact`.
- [x] 8.4 Archive or mark previous workspace inactive.
- [x] 8.5 Create new workspace id.
- [x] 8.6 Update latest pointer.
- [x] 8.7 Reset active transient state.
- [x] 8.8 Add tests for new workspace behavior.

## 9. Resume/list

- [x] 9.1 Implement resume latest.
- [x] 9.2 Implement resume by workspace id.
- [x] 9.3 Implement list workspaces.
- [x] 9.4 Render resume summary.
- [x] 9.5 Add tests for resume/list.

## 10. Export

- [x] 10.1 Implement context bundle export.
- [x] 10.2 Include manifest.json.
- [x] 10.3 Include workspace.json.
- [x] 10.4 Include compact.md when present.
- [x] 10.5 Include context.md.
- [x] 10.6 Include selected artifacts by policy.
- [x] 10.7 Include checksums.
- [x] 10.8 Return `ExportResult`.
- [x] 10.9 Add export tests.

## 11. Commands

- [x] 11.1 Add command parser support for `/context`.
- [x] 11.2 Add `/context status`.
- [x] 11.3 Add `/context compact`.
- [x] 11.4 Add `/context clean`.
- [x] 11.5 Add `/context new`.
- [x] 11.6 Add `/context resume`.
- [x] 11.7 Add `/context list`.
- [x] 11.8 Add `/context export`.
- [x] 11.9 Add convenience aliases `/compact`, `/clean`, `/new`, `/resume`, `/status` where feasible.
- [x] 11.10 Add command tests.

## 12. TUI integration

- [x] 12.1 Create or resume latest workspace on TUI startup.
- [x] 12.2 Show workspace id/title in status/header/footer.
- [x] 12.3 Record submitted inputs to workspace.
- [x] 12.4 Record important command outputs as artifact refs where feasible.
- [x] 12.5 Render `/context` command results in OutputStream.
- [x] 12.6 Show resume summary on startup.
- [x] 12.7 Add TUI tests.

## 13. Assistant integration

- [x] 13.1 Add bounded workspace context provider.
- [x] 13.2 Load `compact.md` and workspace summary.
- [x] 13.3 Do not inject raw unbounded events by default.
- [x] 13.4 Include stale-context caveat metadata.
- [x] 13.5 Fresh warehouse data remains authoritative.
- [x] 13.6 Add tests for context provider.

## 14. Redaction and safety

- [x] 14.1 Reuse existing redaction helpers where available.
- [x] 14.2 Skip or redact sensitive-looking inputs.
- [x] 14.4 Store input kind/length metadata where possible.

- [x] 14.5 Add redaction tests.

## 15. Observability

- [x] 15.1 Emit `WORKSPACE_CREATED`.
- [x] 15.2 Emit `WORKSPACE_RESUMED`.
- [x] 15.3 Emit `WORKSPACE_INPUT_ADDED`.
- [x] 15.4 Emit `WORKSPACE_ARTIFACT_ADDED`.
- [x] 15.5 Emit `WORKSPACE_COMPACTED`.
- [x] 15.6 Emit `WORKSPACE_CLEANED`.
- [x] 15.7 Emit `WORKSPACE_NEW_STARTED`.
- [x] 15.8 Emit `WORKSPACE_EXPORTED`.
- [x] 15.9 Emit `WORKSPACE_ERROR`.
- [x] 15.10 Add observability tests.

## 16. Documentation

- [x] 16.1 Add `vnalpha/docs/workspace-context-lifecycle.md`.
- [x] 16.2 Document concept model.
- [x] 16.3 Document file layout.
- [x] 16.4 Document commands.
- [x] 16.5 Document compact/clean/new/resume/export behavior.
- [x] 16.6 Document safety boundaries.
- [x] 16.7 Document troubleshooting.
- [x] 16.8 Add examples.

## 17. Validation

- [x] 17.1 Run `make test-vnalpha`.
- [x] 17.2 Run `make lint-vnalpha`.
- [x] 17.3 Run `make verify-r4`.
- [x] 17.4 Run `openstock-verify --ci`.
- [x] 17.5 Add validation evidence for lifecycle flow: new -> input -> compact -> status -> export -> new -> resume old.

## Validation evidence

- `VNALPHA_WAREHOUSE_PATH=/tmp/opencode/vnalpha-workspace-lifecycle-$$.duckdb make test-vnalpha`: passed.
- `make lint-vnalpha`: Ruff check passed; all 317 files format-clean.
- `make verify-r4`: passed.
- `./packaging/scripts/openstock-verify --ci`: PASS, 16 OK, 1 existing systemd warning, 0 failures.
- `tests/workspace_context/test_lifecycle_e2e.py` covers new -> input -> compact -> status -> export -> new -> resume old while proving audit logs and raw sensitive input remain outside curated context.
