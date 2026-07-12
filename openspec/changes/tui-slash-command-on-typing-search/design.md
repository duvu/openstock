## Context

The Opencode-like TUI currently routes plain-language and slash commands through a shared
composer input, but the composer shows no discoverability affordance when users type `/`.
Users are required to memorize full command names from `/help` or prior knowledge, and any
mistyped prefix results in an immediate command submission failure.

This change is scoped to `vnalpha` and must preserve the existing command execution path.
Command registration already exists in `vnalpha/commands/registry.py` and is composed by
`CommandExecutor` through `vnalpha/tui/routing/command_path.py`; the UX should only make those
commands visible and easier to select before submit.

Constraints:

- Preserve current read-only research behavior and avoid adding broker, order, or trading-capability
  features.
- Keep execution semantics unchanged: submit text should still go to the same router path.
- Keep suggestions deterministic and independent from chat context history.
- Keep implementation within existing package boundaries (`tui.widgets`, no new external deps).

## Goals / Non-Goals

**Goals:**

- Make slash-command discoverability immediate: typing `/` in the composer SHALL surface a
  suggestion list from registered command names.
- Filter suggestions on each subsequent keystroke while the current text starts with `/`.
- Keep Enter behavior unchanged: the submitted string SHALL still be routed through existing
  `TuiInputRouter` slash-command execution.
- Keep the default rendering lightweight and non-blocking for large registries.

**Non-Goals:**

- Introducing a full-fidelity autocomplete popup component or external completion engine.
- Changing command routing, permission checks, or parser semantics.
- Implementing fuzzy matching or fuzzy ranking beyond deterministic prefix matching.
- Altering command registration, parser execution, or policy surfaces.

## Decisions

1. **Localize suggestion state inside `ComposerInput`**

   - **Choice:** Compute and render suggestion candidates inside the composer widget.
   - **Rationale:** This keeps discoverability logic adjacent to input events (`on_input_changed`)
     and avoids changing `TuiInputRouter` public behavior.
   - **Alternative:** Push suggestions through the router and expose a new UI event stream;
     rejected due to wider blast radius and additional contract changes.

2. **Derive suggestions from `CommandRegistry.names()`**

   - **Choice:** Read the authoritative command list from `vnalpha.commands.registry.CommandRegistry`
     via a deterministic `names()` call.
   - **Rationale:** Reuses existing command source of truth and avoids duplicating command tables in
     UI.
   - **Alternative:** Hardcode a static command list in TUI code; rejected as it will drift from
     actual registry semantics over time.

3. **Prefix-based filtering with fallback empty-state handling**

   - **Choice:** For composer text beginning with `/`, strip only the leading `/` and filter names by
     `name.startswith(prefix)` (case-insensitive); when the prefix is empty, show all commands.
   - **Rationale:** Predictable behavior for first-party commands and fast incremental filtering.
   - **Alternative:** Substring/regex matching; rejected because it can surface unexpectedly noisy
     results for short command names.

4. **Simple static list rendering (`Static` widget)**

   - **Choice:** Add a dedicated suggestion panel inside `ComposerInput`, visible while `/` mode is
     active and hidden otherwise.
   - **Rationale:** Minimal UI change using primitives already in place and no new layout protocol.
   - **Alternative:** Use a dedicated autocomplete overlay component; rejected due to larger
     dependency and interaction complexity in this codebase stage.

## Risks / Trade-offs

- **[Risk] Textual event churn on every key press** → **Mitigation:** filtering is in-memory over a
  short command name list and bounded by a short-circuit when suggestions are hidden.
- **[Risk] Duplicate command registries across runtime contexts** → **Mitigation:** suggestions are
  generated from the same construction path used by command execution and filtered purely from command
  names, so mismatches are detectable by integration tests.
- **[Risk] Focus/selection confusion for keyboard-only users** → **Mitigation:** keep behavior
  additive: suggestions display only; Enter/Tab/arrow actions still use existing route and history
  semantics.

## Migration Plan

1. Add command suggestion rendering and filtering in `ComposerInput`.
2. Add targeted tests covering `/` activation, filtering, and non-disruptive Enter submission.
3. Run the relevant TUI tests and adjust fixtures if needed.
4. Keep code path off by default if textual is unavailable (fallback class behavior remains.
   unchanged).

Rollback strategy:

- If any regression appears, remove the suggestion panel widget lines from
  `composer_input.py` and restore prior behavior.
- No data migration or schema rollback is required because behavior is UI-only.

## Open Questions

The following open questions were resolved during implementation:

- **List length cap** — Capped at `_max_suggestions = 10` (panel `max-height: 12`, composer
  `max-height: 16`) so the matched set stays visible without clipping on normal terminal heights.
- **`//` behavior** — Left as prefix filtering: `//` still starts with `/` and filters command
  names by the `//` body, which matches no command and clears the list. No special-casing added.
- **Names vs descriptions** — Show command names only (e.g. `/help`), keeping the panel compact and
  deterministic; descriptions remain available via `/help`.

### Additional hardening (focus + clipping)

Typing `/` only reveals the list when keystrokes reach the composer `Input`. Two robustness gaps
were closed:

- The app now sets `AUTO_FOCUS = "#composer-input-field"` so the composer Input owns focus at
  launch instead of relying solely on a deferred `call_after_refresh`.
- The output `RichLog` is made non-focusable (`can_focus = False`) so it can never steal keyboard
  focus (e.g. when the user clicks the output area), which would otherwise prevent `Input.Changed`
  from firing and hide the suggestion list.
