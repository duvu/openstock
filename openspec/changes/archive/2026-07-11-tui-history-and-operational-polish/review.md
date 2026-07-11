# Review: TUI history and operational polish gaps

## Verdict

The TUI has moved in the right architectural direction by adopting an opencode-like single-stream model. However, it is not yet a complete terminal-agent workspace.

Current likely state:

```text
single output stream: mostly implemented
single composer input: mostly implemented
keyboard input history: missing or incomplete
operational status UI: incomplete
visual hierarchy: functional but not polished enough
long-running action feedback: incomplete
```

Target state:

```text
polished terminal research console with history navigation and visible runtime state
```

## Current strengths

### 1. Correct interaction model

The TUI should continue to use:

```text
OutputStream
ComposerInput
```

This should remain the default. The implementation must not reintroduce the old multi-screen dashboard or separate command history panel.

### 2. Unified output path

Assistant answers, command results, tool traces, warnings, and errors should continue rendering into the same output stream.

### 3. Closed-loop logging foundation

The codebase already has file-based observability. The TUI refinement should use it rather than creating a second ad-hoc logging path.

## Blocking gaps

### 1. Missing input history navigation

The composer needs shell-like history behavior:

```text
Up       previous input
Down     next input
Ctrl+P   previous input, optional
Ctrl+N   next input, optional
```

This should work for both slash commands and natural-language prompts.

### 2. Draft preservation

When the user types a new draft, presses Up to inspect history, then presses Down past the newest history item, the original draft should be restored.

Example:

```text
history: /explain FPT, /compare FPT MWG
current draft: /explain HPG
press Up    -> /compare FPT MWG
press Up    -> /explain FPT
press Down  -> /compare FPT MWG
press Down  -> /explain HPG
```

### 3. No separate history panel

History must affect the composer input value only. It must not create a separate visible command history pane.

### 4. Status state is not first-class

The user needs a compact operational view. Examples:

```text
READY
RUNNING /explain FPT
SYNCING FPT OHLCV
BUILDING FEATURES
SCORING
ASSISTANT THINKING
TOOL candidate.explain
WARNING
ERROR
SERVICE UNAVAILABLE
```

### 5. Long-running operations need visible progress

Auto data provisioning can be slow. The TUI should show progress during:

```text
symbol sync
OHLCV sync
benchmark sync
canonical build
feature build
scoring
assistant plan/execution/synthesis
```

### 6. Visual hierarchy needs refinement

The output stream should be readable under real use:

```text
user messages distinct from assistant messages
commands distinct from command results
tool trace compact but visible
warnings/errors obvious
status line compact
keyboard hints unobtrusive
```

## Risks

### Risk: reintroducing dashboard complexity

Adding status UI must not reintroduce multiple work panes. Status should be compact and operational.

### Risk: history leaks sensitive text

If persistent history is implemented, it must be redaction-aware and optionally disabled. The first implementation can be in-session only if persistence risk is not resolved.

### Risk: history conflicts with cursor movement

If the composer supports multiline input later, Up/Down behavior may conflict with cursor movement. For the current single-line composer, Up/Down should navigate history.

### Risk: flaky TUI tests

Tests should assert behavior and DOM constraints, not exact colors or pixel layout.

## Recommended architecture

```text
ComposerInput
  -> InputHistory
       -> push(text)
       -> previous(current_draft)
       -> next()
       -> reset_navigation()

VnAlphaApp / TuiInputRouter
  -> RuntimeStatus
       -> set_idle()
       -> set_running(label)
       -> set_warning(label)
       -> set_error(label)
       -> set_progress(label, detail)

OutputStream
  -> standardized message block rendering
```

Optional persistent history:

```text
~/.local/share/vnalpha/tui_history.jsonl
or
warehouse table tui_input_history
```

Prefer in-session history first unless persistence is implemented with clear limits and redaction safeguards.

## Definition of done

The TUI is considered complete for this scope when:

```text
- history navigation works exactly like a terminal composer
- runtime states are visible and tested
- visual output is readable and consistent
- default layout remains opencode-like
- tests cover critical keyboard and state transitions
- documentation explains keybindings and states
```
