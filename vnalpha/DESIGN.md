# vnalpha TUI design contract

## 1. Product character

The TUI is a quiet, keyboard-first research workspace: dense enough for evidence, restrained enough for long sessions, and explicit about status and missing data. It should feel like an analytical terminal, not a trading screen.

## 2. Signature structure

One transcript is the primary workspace and the only persistent scrolling owner. Conversation, activity, final research results, TODO output, and artifact navigation all appear there. A bounded debug-log drawer may temporarily occupy space below it; no right-side rail competes with the transcript.

## 3. Color and emphasis

Use Textual semantic tokens only: `$background`, `$surface`, `$surface-darken-1`, `$primary`, `$text`, `$text-muted`, `$warning`, and `$error`. Ordinary transcript rows remain unboxed. Successful final results receive one subtle border and surface tone; warnings and errors use their semantic colors without implying success.

## 4. Type and text

The terminal's monospace face is authoritative. Use weight and semantic color sparingly for result titles, status, and keyboard hints. User-facing and copyable text must remain readable without color and must contain no ANSI controls or Rich markup.

## 5. Spacing and layout

Use a one-cell base rhythm. Status and footer are one row each; the composer owns its content-driven height. The transcript consumes `1fr`. When open, the log drawer receives a height bounded by the terminal while preserving useful transcript space. Borders provide grouping; nested cards and decorative padding are avoided.

## 6. Components and states

- `StatusBar`: compact global state and workspace context.
- `OutputStream`: transcript plus bordered `ResultPresentation` blocks; retains canonical plain text independently of Rich rendering.
- `DebugLogDrawer`: hidden by default, one shared tail source, compact level control, filtered redacted output.
- `ComposerInput`: always returns focus after layout actions and keeps height-aware suggestions.
- `Footer`: concise keyboard discovery, including PgUp/PgDn transcript scrolling, F12 logs, and Ctrl+Y result copy when width permits. Home/End jump to transcript boundaries without moving focus from the composer.

Empty, partial, failed, busy, missing-file, and unsupported-clipboard states must be visible and truthful. They must not be styled as successful results.

## 7. Motion and interaction

Terminal layout changes are immediate. F12 toggles the inline drawer without screen navigation or spawning another worker. Ctrl+Y copies the latest final result. `/copy` commands are local UI actions handled even while research routing is busy. No mouse-only behavior is required.

## 8. Accessibility and constraints

All primary actions are keyboard reachable. Meaning never depends on color alone. Required layouts are 80x20, 100x24, 120x30, and 160x50 with non-intersecting regions. Research-only safety, file-only TUI logging, bounded retained state, secret redaction, and plain-text clipboard output are invariant constraints.
