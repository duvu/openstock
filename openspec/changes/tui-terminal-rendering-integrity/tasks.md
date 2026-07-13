# Tasks: TUI Terminal Rendering Integrity

## How to use this checklist

Execute tasks in order unless a task explicitly declares independent work.

Do not mark a task complete from PR prose alone. A checked task requires the code and evidence named by the task.

## 0. Governance and baseline

- [ ] **0.1 Confirm the change remains a TUI/logging integrity fix.** No research command semantics, assistant policy, or trading-related capability may be added. [evidence: diff review and safety regression tests]
- [ ] **0.2 Link implementation work to GitHub issue #60.** [evidence: PR body]
- [ ] **0.3 Record implementation base SHA and current TUI/logging test status in `validation.md`.** [evidence: command rows]
- [ ] **0.4 Capture a reproducible terminal-frame corruption case or, if nondeterministic, a deterministic stderr-bypass test that proves the same root cause.** [evidence: test or sanitized transcript]
- [ ] **0.5 Confirm no overlapping active OpenSpec already owns surface-aware TUI logging and geometry integrity.** `tui-research-workflow-polish` remains responsible for research workflow presentation, not terminal ownership. [evidence: OpenSpec review note]

## 1. Surface-aware logging model

- [ ] **1.1 Add a typed logging surface model** with at least `cli`, `tui`, and `test`. [files: `core/logging.py` or focused logging config module] [evidence: unit tests]
- [ ] **1.2 Preserve backward-compatible CLI behavior** when callers omit the surface. [evidence: CLI logging test]
- [ ] **1.3 Assign stable identities to OpenStock-owned queue, file, and console handlers.** [evidence: handler inspection test]
- [ ] **1.4 Replace the one-shot `_CONFIGURED` behavior with idempotent handler reconciliation.** [depends: 1.1, 1.3] [evidence: repeated-configuration test]
- [ ] **1.5 Preserve unrelated third-party/root handlers while reconciling OpenStock-owned handlers.** [depends: 1.4] [evidence: foreign-handler preservation test]
- [ ] **1.6 Ensure only one active queue listener/file pipeline exists after repeated configuration.** [depends: 1.4] [evidence: listener/handler count test]
- [ ] **1.7 Stop obsolete OpenStock queue listeners safely when configuration changes.** [depends: 1.4] [evidence: transition lifecycle test]
- [ ] **1.8 Keep canonical rotating JSON file logging active for CLI and TUI surfaces.** [evidence: file-output tests]
- [ ] **1.9 Disable OpenStock-owned console/stderr diagnostic logging in TUI surface.** [depends: 1.4] [evidence: captured-stderr test]
- [ ] **1.10 Retain console diagnostics for non-TUI CLI surface.** [depends: 1.4] [evidence: captured-stderr test]
- [ ] **1.11 Do not fall back to direct stderr logging if TUI file logging fails.** Report the problem through a bounded in-app warning or startup result. [evidence: injected file-handler failure test]

## 2. CLI and TUI integration

- [ ] **2.1 Configure the initial CLI surface in the root command callback.** [depends: 1.1–1.10] [files: `cli_app/common.py`] [evidence: CLI invocation test]
- [ ] **2.2 Reconcile logging to TUI surface before `VnAlphaApp.run()` takes terminal ownership.** [depends: 1.9] [files: `cli_app/tui.py`] [evidence: TUI invocation test]
- [ ] **2.3 Verify the transition `CLI → TUI` removes only the OpenStock console handler.** [evidence: handler transition test]
- [ ] **2.4 Verify the sequence `CLI → TUI → TUI → CLI` is idempotent and restores expected console behavior exactly once.** [evidence: transition matrix test]
- [ ] **2.5 Confirm intentional Typer/Rich command output is not suppressed by diagnostic-handler changes.** [evidence: CLI command-output regression test]
- [ ] **2.6 Confirm F12 LogScreen continues to read the same structured log file.** [evidence: file-tail integration test]

## 3. Main workspace containment

- [ ] **3.1 Define Screen as a fixed application frame with no whole-screen overflow scrolling.** [files: `tui/app.py`] [evidence: geometry test]
- [ ] **3.2 Add explicit `min-height: 0` and overflow containment to `#main-body`.** [evidence: geometry test]
- [ ] **3.3 Add explicit containment to `#output-column`.** [evidence: geometry test]
- [ ] **3.4 Add explicit containment to `OutputStream`.** [files: `widgets/output_stream.py`] [evidence: geometry test]
- [ ] **3.5 Make the nested transcript RichLog the sole scrolling owner for transcript content.** [depends: 3.1–3.4] [evidence: scroll and region test]
- [ ] **3.6 Keep composer and footer anchored below `main-body` under long transcript output.** [depends: 3.1–3.5] [evidence: wrapped-line geometry test]
- [ ] **3.7 Preserve existing transcript navigation, structured message rendering, and artifact-detail restoration.** [evidence: existing and new regression tests]

## 4. Height-aware composer suggestions

- [ ] **4.1 Extend responsive policy inputs to include terminal height.** [files: `tui/responsive_layout.py`] [evidence: policy unit tests]
- [ ] **4.2 Define compact, medium, and full suggestion capacities.** [depends: 4.1] [evidence: policy boundary tests]
- [ ] **4.3 Add a public ComposerInput API to update the suggestion limit without rebuilding the registry.** [files: `widgets/composer_input.py`] [evidence: widget unit test]
- [ ] **4.4 Apply suggestion capacity on mount and resize.** [depends: 4.1–4.3] [files: `tui/app.py`] [evidence: pilot tests]
- [ ] **4.5 Preserve a usable transcript minimum while suggestions are open.** [evidence: `80x20` and `100x24` geometry tests]
- [ ] **4.6 Add a documented compact-footer behavior when terminal height cannot fit the normal footer.** [evidence: responsive test]
- [ ] **4.7 Preserve command filtering, submission, history, and fallback command-list behavior.** [evidence: existing composer tests]

## 5. TODO rail containment

- [ ] **5.1 Give TodoPanel an explicit flexible height and zero minimum height within `main-body`.** [files: `widgets/todo_panel.py`] [evidence: geometry test]
- [ ] **5.2 Add an explicit vertical scrolling or bounded truncation owner for TODO content.** [evidence: long-list interaction test]
- [ ] **5.3 Seed at least 50 TODO/warning items and prove the rail remains inside `main-body`.** [evidence: headless pilot]
- [ ] **5.4 Preserve current responsive visibility and toggle behavior.** [evidence: existing TODO tests]
- [ ] **5.5 Preserve composer focus when the TODO rail is shown, hidden, or resized.** [evidence: focus test]

## 6. F12 LogScreen integrity

- [ ] **6.1 Give LogScreen an explicit opaque background and fixed screen ownership.** [files: `tui/screens/log_viewer.py`] [evidence: screen geometry test]
- [ ] **6.2 Introduce a bounded log body with `height: 1fr`, zero minimum height, and contained overflow.** [evidence: short-terminal test]
- [ ] **6.3 Keep the log RichLog as the sole scrolling owner inside LogScreen.** [evidence: scroll test]
- [ ] **6.4 Add explicit `Esc` behavior to close LogScreen.** [evidence: pilot test]
- [ ] **6.5 Prove printable input does not modify the underlying composer while LogScreen is active.** [depends: 6.4] [evidence: input-isolation test]
- [ ] **6.6 Make level filtering usable on narrow terminals through a compact selector, bounded wrapping, or keyboard bindings.** [evidence: `80x20` LogScreen test]
- [ ] **6.7 Bound in-memory log records or document and create a follow-up issue for pagination if deliberately deferred.** [evidence: implementation or linked issue]
- [ ] **6.8 Preserve ANSI/control-sequence sanitization and existing level semantics.** [evidence: existing log-viewer tests]

## 7. Geometry and terminal-integrity regression suite

- [ ] **7.1 Add a reusable assertion for workspace region non-intersection.** [files: TUI test helpers] [evidence: helper used across tests]
- [ ] **7.2 Test default workspace geometry at `80x20`, `100x24`, `120x30`, and `160x50`.** [evidence: parametrized test]
- [ ] **7.3 Repeat geometry tests with slash suggestions open.** [evidence: parametrized test]
- [ ] **7.4 Repeat geometry tests with long wrapped transcript content.** [evidence: parametrized test]
- [ ] **7.5 Repeat geometry tests with long TODO content and both allowed visibility states.** [evidence: parametrized test]
- [ ] **7.6 Push LogScreen and verify its toolbar/body/log regions stay within the active screen.** [evidence: screen-region test]
- [ ] **7.7 Emit logging events during a mounted TUI and prove direct stderr remains empty while the file receives the event.** [evidence: integration test]
- [ ] **7.8 Verify no duplicate log file records are produced after repeated surface configuration.** [evidence: exact-count test]
- [ ] **7.9 Verify user results and errors still render through OutputStream/typed messages rather than logger stderr.** [evidence: routing test]

## 8. Observability and failure UX

- [ ] **8.1 Add bounded logging-surface configuration observability.** Include surface and boolean file/console state only. [evidence: event test]
- [ ] **8.2 Do not emit high-volume resize/layout events by default.** [evidence: source review]
- [ ] **8.3 Surface TUI logging initialization failure through an in-app warning with a stable error ID.** [depends: 1.11] [evidence: injected failure test]
- [ ] **8.4 Do not expose raw filesystem secrets or handler representations in UI or logs.** [evidence: redaction test]

## 9. Focused validation gates

- [ ] **9.1 Run focused Ruff checks for logging, CLI integration, TUI widgets/screens, and changed tests.** [evidence: command row]
- [ ] **9.2 Run focused Ruff format check.** [evidence: command row]
- [ ] **9.3 Run focused TUI, routing, structured-message, TODO, composer, and log-viewer tests.** [evidence: command row]
- [ ] **9.4 Run existing CLI/logging tests.** [evidence: command row]
- [ ] **9.5 Run relevant research-only policy and safety regression tests.** [evidence: command row]
- [ ] **9.6 Perform manual QA at one short terminal and one wide terminal under visible log traffic.** [evidence: sanitized notes or recording]
- [ ] **9.7 Confirm F12 displays new file-backed records while direct terminal stderr stays clean.** [evidence: manual and automated evidence]
- [ ] **9.8 Record final tested commit SHA and residual risks in `validation.md`.** [evidence: final ledger]

## 10. Documentation and closure

- [ ] **10.1 Document logging surface behavior for operators and developers.** [files: TUI/logging docs]
- [ ] **10.2 Document responsive height behavior and supported minimum viewport.** [files: TUI docs]
- [ ] **10.3 Link implementation PR and validation evidence from issue #60.** [evidence: issue comment]
- [ ] **10.4 Update `tui-research-workflow-polish` dependency/evidence after rendering integrity is implemented.** [evidence: OpenSpec registry update]
- [ ] **10.5 Archive this OpenSpec only after runtime code, tests, evidence, and accepted delta synchronization are complete.**