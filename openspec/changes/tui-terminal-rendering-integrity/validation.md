# Validation: TUI Terminal Rendering Integrity

## Status

```text
OpenSpec authored: yes
Runtime implementation: not started
Issue: #60
Validation commands executed: OpenSpec/source review only
Runtime gate: pending
```

This ledger must be updated by the implementation PR. Do not replace `pending` with `pass` without command evidence for the tested commit.

## Baseline findings

| Area | Current finding | Required evidence |
|---|---|---|
| Logging ownership | Root logging config installs a direct console/stderr handler before Textual starts | surface-transition unit/integration tests |
| Logging idempotency | Module-global configured flag cannot reconcile CLI to TUI behavior | repeated configuration matrix |
| Main layout | output, composer, footer, and parent overflow boundaries are not validated by runtime regions | headless geometry matrix |
| Composer | suggestions can request most of a short viewport and policy is width-centric | height-aware policy and pilot tests |
| TODO rail | content has no explicit bounded scrolling owner | 50-item region test |
| LogScreen | screen/body geometry and underlying input isolation are not tested | pushed-screen geometry and input tests |
| Existing tests | focus/display/CSS assertions do not prove non-overlap | actual `region` assertions |

## Evidence row format

| UTC timestamp | Commit SHA | Task | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|

## OpenSpec evidence

| UTC timestamp | Commit SHA | Task | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-13T00:00:00Z | OpenSpec branch | 0.2 | Review GitHub issue #60 | 0 | Issue records terminal stderr and layout-overflow findings plus acceptance criteria | GitHub issue #60 |
| 2026-07-13T00:00:00Z | OpenSpec branch | 0.5 | Review `openspec/active-changes.yaml` and `tui-research-workflow-polish` proposal | 0 | Rendering integrity is a distinct prerequisite; research workflow polish remains responsible for artifact presentation | OpenSpec diff |
| 2026-07-13T00:00:00Z | OpenSpec branch | design | Inspect logging, CLI startup, TUI app, OutputStream, ComposerInput, TodoPanel, LogScreen, and existing tests | 0 | Confirmed direct stderr path and missing geometry/terminal-integrity regression coverage | proposal/design/spec |

Timestamps above identify the documentation session and must not be reused as runtime validation evidence.

## Required implementation commands

Run focused lint and format checks:

```bash
cd vnalpha
ruff check \
  src/vnalpha/core/logging.py \
  src/vnalpha/cli_app/common.py \
  src/vnalpha/cli_app/tui.py \
  src/vnalpha/tui \
  tests/test_tui.py \
  tests/test_tui_routing.py \
  tests/test_tui_todo_panel.py \
  tests/test_tui_log_viewer.py

ruff format --check \
  src/vnalpha/core/logging.py \
  src/vnalpha/cli_app/common.py \
  src/vnalpha/cli_app/tui.py \
  src/vnalpha/tui \
  tests/test_tui.py \
  tests/test_tui_routing.py \
  tests/test_tui_todo_panel.py \
  tests/test_tui_log_viewer.py
```

Run focused tests:

```bash
cd vnalpha
pytest -q \
  tests/test_tui.py \
  tests/test_tui_routing.py \
  tests/test_tui_todo_panel.py \
  tests/test_tui_log_viewer.py \
  tests/test_tui_structured_messages.py
```

Run existing logging and CLI tests selected by the implementation diff:

```bash
cd vnalpha
pytest -q tests -k 'logging or cli or tui'
```

Run policy/safety regressions:

```bash
cd vnalpha
pytest -q \
  tests/test_chat_safety.py \
  tests/test_policy_capabilities.py \
  tests/test_safety_boundary.py
```

The exact existing test paths may be adjusted if names differ on the implementation base. The evidence ledger must record the actual commands used.

## Required viewport matrix

| Viewport | Default | Suggestions open | Long transcript | Long TODO | LogScreen |
|---|---:|---:|---:|---:|---:|
| `80x20` | pending | pending | pending | pending | pending |
| `100x24` | pending | pending | pending | pending | pending |
| `120x30` | pending | pending | pending | pending | pending |
| `160x50` | pending | pending | pending | pending | pending |

Every tested state must assert actual widget-region containment rather than only checking CSS strings.

## Required logging transition matrix

| Transition | File output | Console output | Duplicate-free | Status |
|---|---:|---:|---:|---|
| fresh → CLI | required | required | required | pending |
| fresh → TUI | required | forbidden | required | pending |
| CLI → TUI | required | forbidden after transition | required | pending |
| TUI → TUI | required | forbidden | required | pending |
| TUI → CLI | required | required after transition | required | pending |
| CLI → TUI → TUI → CLI | required | surface-correct | required | pending |

## Manual QA checklist

### Short terminal

```text
Suggested size: 80x20 or equivalent
```

- [ ] Start TUI with INFO or DEBUG logging enabled.
- [ ] Submit a natural-language request that emits classifier/router logs.
- [ ] Open slash suggestions.
- [ ] Verify transcript, input, and footer remain readable.
- [ ] Verify no diagnostic log text appears outside Textual widgets.
- [ ] Open and close F12 LogScreen.
- [ ] Verify underlying composer text is unchanged.

### Wide terminal

```text
Suggested size: 160x50 or equivalent
```

- [ ] Show TODO rail and seed long content.
- [ ] Append long transcript/table output.
- [ ] Verify TODO and transcript scroll independently.
- [ ] Verify composer and footer remain anchored.
- [ ] Verify structured logs are visible in F12 LogScreen.

## Final gate

The change may be marked complete only when:

```text
- every required task has code and evidence;
- all required viewport states pass;
- all logging transitions pass;
- direct TUI stderr output is absent;
- existing TUI and safety regressions pass;
- manual QA confirms short and wide terminal behavior;
- the tested commit SHA is recorded;
- residual risks are documented.
```