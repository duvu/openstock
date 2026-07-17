# Validation Ledger

## Scope and status

The implementation remains a research-only TUI and logging integrity change.
No assistant policy, research command semantics, data provisioning behavior, or
trading-related capability changed.

Implementation base SHA:
`1de8636faed167b7fb0c7b038153eaeeb83f09ce`. The current implementation is
uncommitted by user instruction, so exact candidate SHA and CI evidence remain
pending.

## Automated evidence

| Command | Result |
|---|---|
| `uv run ruff check` on changed logging, CLI, TUI, and test files | Passed |
| `uv run ruff format --check` on changed files | Passed |
| `cd vnalpha && uv run pytest -q tests/test_tui_result_presentation.py tests/test_tui_clipboard.py tests/test_tui_log_viewer.py tests/test_tui_terminal_integrity.py tests/test_tui_routing.py tests/test_tui_workspace.py` | `76 passed` |
| Required viewport geometry and terminal-buffer assertions | Passed at `80x20`, `100x24`, `120x30`, and `160x50` |
| Independent TUI design-integrity review | Passed after four review/fix iterations |
| Independent terminal-precision review | Passed after three review/fix iterations |
| `uv run vnalpha --help` | Passed |
| `uv run vnalpha tui --help` | Passed |

The focused suite covers surface transitions, foreign handler preservation,
file-only TUI logs, injected file-handler failure, workspace geometry at
`80x20`, `100x24`, `120x30`, and `160x50`, open suggestions, long task
results, inline-drawer focus/scroll preservation, bounded copied records, and
file-backed drawer output.

## Manual QA

| Viewport | Observed result |
|---|---|
| `80x20` | The status bar, bounded transcript, composer, and footer rendered without direct diagnostic text overwriting the Textual frame. |
| `160x50` | The full-width workspace remained contained; F12 opened the inline file-backed drawer, Esc hid it without screen navigation, and the application exited cleanly. |

## Residual work

GitHub issue/PR linkage, exact-candidate CI, and archive synchronization remain
pending. The accepted async-logging contract is synchronized with the inline
drawer below; external live acceptance is tracked by #162, #180, #181, and
#193 rather than treated as local TUI evidence.
