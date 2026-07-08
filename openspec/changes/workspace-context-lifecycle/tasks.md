# Tasks: Workspace context lifecycle

## 0. Governance

- [ ] 0.1 Treat workspace context as curated working memory, not raw transcript dump.
- [ ] 0.2 Keep audit logs separate and immutable.
- [ ] 0.3 Do not delete audit logs during clean/new lifecycle operations.
- [ ] 0.4 Apply redaction/sensitive-content rules before storing workspace text.
- [ ] 0.5 Keep fresh warehouse data authoritative over stale workspace summaries.
- [ ] 0.6 Do not mark complete without code, tests, and validation evidence.

## 1. Workspace package

- [ ] 1.1 Add `vnalpha/src/vnalpha/workspace_context/__init__.py`.
- [ ] 1.2 Add `models.py`.
- [ ] 1.3 Add `storage.py`.
- [ ] 1.4 Add `lifecycle.py`.
- [ ] 1.5 Add `compaction.py`.
- [ ] 1.6 Add `cleaning.py`.
- [ ] 1.7 Add `export.py`.
- [ ] 1.8 Add `integration.py`.
- [ ] 1.9 Add `observability.py`.

## 2. Workspace models

- [ ] 2.1 Define `WorkspaceState`.
- [ ] 2.2 Define `WorkspaceArtifactRef`.
- [ ] 2.3 Define `WorkspaceInputRef`.
- [ ] 2.4 Define `WorkspaceTask`.
- [ ] 2.5 Define `WorkspaceStatusReport`.
- [ ] 2.6 Define `CompactionResult`.
- [ ] 2.7 Define `CleanPlan`.
- [ ] 2.8 Define `CleanResult`.
- [ ] 2.9 Define `ExportResult`.
- [ ] 2.10 Add serialization/deserialization tests.

## 3. Storage

- [ ] 3.1 Implement configurable workspace root.
- [ ] 3.2 Default root to `.vnalpha/workspaces` or configured data root.
- [ ] 3.3 Implement `latest.json` pointer.
- [ ] 3.4 Implement `index.json` workspace index.
- [ ] 3.5 Implement workspace directory creation.
- [ ] 3.6 Implement atomic JSON writes.
- [ ] 3.7 Implement JSONL event append.
- [ ] 3.8 Implement basic lock file.
- [ ] 3.9 Add tests for atomic write and load.

## 4. Workspace lifecycle

- [ ] 4.1 Implement `get_or_create_latest_workspace()`.
- [ ] 4.2 Implement `create_workspace()`.
- [ ] 4.3 Implement `resume_workspace()`.
- [ ] 4.4 Implement `list_workspaces()`.
- [ ] 4.5 Implement `archive_workspace()`.
- [ ] 4.6 Implement `get_status()`.
- [ ] 4.7 Implement `record_input()`.
- [ ] 4.8 Implement `record_artifact()`.
- [ ] 4.9 Implement `record_warning()`.
- [ ] 4.10 Implement `record_error()`.
- [ ] 4.11 Add lifecycle tests.

## 5. Context files

- [ ] 5.1 Generate `workspace.json`.
- [ ] 5.2 Generate/update `context.md`.
- [ ] 5.3 Generate/update `events.jsonl`.
- [ ] 5.4 Create `artifacts/` directory.
- [ ] 5.5 Create `archive/` directory.
- [ ] 5.6 Create `exports/` directory.
- [ ] 5.7 Add tests for file layout.

## 6. Compaction

- [ ] 6.1 Implement deterministic compaction from workspace state and curated events.
- [ ] 6.2 Include current goal, active symbols/date, findings, assumptions, decisions, open tasks, warnings, and source refs.
- [ ] 6.3 Avoid raw audit log ingestion by default.
- [ ] 6.4 Write `compact.md`.
- [ ] 6.5 Return `CompactionResult`.
- [ ] 6.6 Update `last_compacted_at`.
- [ ] 6.7 Emit workspace and audit events.
- [ ] 6.8 Add compaction tests.

## 7. Cleaning

- [ ] 7.1 Implement clean dry-run.
- [ ] 7.2 Implement clean plan classification: keep/archive/remove/needs_confirmation.
- [ ] 7.3 Implement archive-first cleanup.
- [ ] 7.4 Support resolved-errors cleanup.
- [ ] 7.5 Support old-events cleanup.
- [ ] 7.6 Support artifact cleanup.
- [ ] 7.7 Protect audit logs, compact.md, workspace.json, pinned items, and user notes.
- [ ] 7.8 Return `CleanResult`.
- [ ] 7.9 Add cleaning tests.

## 8. New workspace

- [ ] 8.1 Implement `/context new` service behavior.
- [ ] 8.2 Compact current workspace by default.
- [ ] 8.3 Support `--no-compact`.
- [ ] 8.4 Archive or mark previous workspace inactive.
- [ ] 8.5 Create new workspace id.
- [ ] 8.6 Update latest pointer.
- [ ] 8.7 Reset active transient state.
- [ ] 8.8 Add tests for new workspace behavior.

## 9. Resume/list

- [ ] 9.1 Implement resume latest.
- [ ] 9.2 Implement resume by workspace id.
- [ ] 9.3 Implement list workspaces.
- [ ] 9.4 Render resume summary.
- [ ] 9.5 Add tests for resume/list.

## 10. Export

- [ ] 10.1 Implement context bundle export.
- [ ] 10.2 Include manifest.json.
- [ ] 10.3 Include workspace.json.
- [ ] 10.4 Include compact.md when present.
- [ ] 10.5 Include context.md.
- [ ] 10.6 Include selected artifacts by policy.
- [ ] 10.7 Include checksums.
- [ ] 10.8 Return `ExportResult`.
- [ ] 10.9 Add export tests.

## 11. Commands

- [ ] 11.1 Add command parser support for `/context`.
- [ ] 11.2 Add `/context status`.
- [ ] 11.3 Add `/context compact`.
- [ ] 11.4 Add `/context clean`.
- [ ] 11.5 Add `/context new`.
- [ ] 11.6 Add `/context resume`.
- [ ] 11.7 Add `/context list`.
- [ ] 11.8 Add `/context export`.
- [ ] 11.9 Add convenience aliases `/compact`, `/clean`, `/new`, `/resume`, `/status` where feasible.
- [ ] 11.10 Add command tests.

## 12. TUI integration

- [ ] 12.1 Create or resume latest workspace on TUI startup.
- [ ] 12.2 Show workspace id/title in status/header/footer.
- [ ] 12.3 Record submitted inputs to workspace.
- [ ] 12.4 Record important command outputs as artifact refs where feasible.
- [ ] 12.5 Render `/context` command results in OutputStream.
- [ ] 12.6 Show resume summary on startup.
- [ ] 12.7 Add TUI tests.

## 13. Assistant integration

- [ ] 13.1 Add bounded workspace context provider.
- [ ] 13.2 Load `compact.md` and workspace summary.
- [ ] 13.3 Do not inject raw unbounded events by default.
- [ ] 13.4 Include stale-context caveat metadata.
- [ ] 13.5 Fresh warehouse data remains authoritative.
- [ ] 13.6 Add tests for context provider.

## 14. Redaction and safety

- [ ] 14.1 Reuse existing redaction helpers where available.
- [ ] 14.2 Skip or redact sensitive-looking inputs.
- [ ] 14.3 Avoid logging raw full input in audit events.
- [ ] 14.4 Store input kind/length metadata where possible.
- [ ] 14.5 Add redaction tests.

## 15. Observability

- [ ] 15.1 Emit `WORKSPACE_CREATED`.
- [ ] 15.2 Emit `WORKSPACE_RESUMED`.
- [ ] 15.3 Emit `WORKSPACE_INPUT_ADDED`.
- [ ] 15.4 Emit `WORKSPACE_ARTIFACT_ADDED`.
- [ ] 15.5 Emit `WORKSPACE_COMPACTED`.
- [ ] 15.6 Emit `WORKSPACE_CLEANED`.
- [ ] 15.7 Emit `WORKSPACE_NEW_STARTED`.
- [ ] 15.8 Emit `WORKSPACE_EXPORTED`.
- [ ] 15.9 Emit `WORKSPACE_ERROR`.
- [ ] 15.10 Add observability tests.

## 16. Documentation

- [ ] 16.1 Add `vnalpha/docs/workspace-context-lifecycle.md`.
- [ ] 16.2 Document concept model.
- [ ] 16.3 Document file layout.
- [ ] 16.4 Document commands.
- [ ] 16.5 Document compact/clean/new/resume/export behavior.
- [ ] 16.6 Document safety boundaries.
- [ ] 16.7 Document troubleshooting.
- [ ] 16.8 Add examples.

## 17. Validation

- [ ] 17.1 Run `make test-vnalpha`.
- [ ] 17.2 Run `make lint-vnalpha`.
- [ ] 17.3 Run `make verify-r4`.
- [ ] 17.4 Run `openstock-verify --ci`.
- [ ] 17.5 Add validation evidence for lifecycle flow: new -> input -> compact -> status -> export -> new -> resume old.
