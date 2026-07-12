## 1. OpenSpec Compliance

- [x] 1.1 Ensure design.md exists, references proposal intent, and records deterministic suggestion behavior.
- [x] 1.2 Ensure specs include modified ComposerInput behavior for slash-command suggestions and filtering.
- [x] 1.3 Run `openspec status --change "tui-slash-command-on-typing-search"` and confirm `tasks` is now unblocked.

## 2. UI Implementation

- [x] 2.1 Add command suggestion rendering container and visibility control in `vnalpha/src/vnalpha/tui/widgets/composer_input.py`.
- [x] 2.2 Build deterministic command lookup and prefix filtering logic for `/`-prefixed input.
- [x] 2.3 Wire text-change event handling so suggestion list updates on each keystroke and clears otherwise.
- [x] 2.4 Ensure submit flow remains unchanged (`ComposerSubmitted` still emitted with the exact entered text).

## 3. Test Coverage

- [x] 3.1 Add/adjust tests in `vnalpha/tests/test_tui.py` validating suggestion visibility after typing `/`.
- [x] 3.2 Add/adjust tests validating prefix filtering while typing `/c`, `/co`, etc.
- [x] 3.3 Add/adjust tests validating command submission still routes via existing `ComposerSubmitted` flow.

## 4. Validation

- [x] 4.1 Run focused unit tests (`vnalpha/tests/test_tui.py`, `vnalpha/tests/test_command_registry.py` if impacted).
- [x] 4.2 Run `lsp_diagnostics` on changed Python files.
- [x] 4.3 Re-run `openspec status --change "tui-slash-command-on-typing-search"` and capture final evidence.

## 5. Robustness Hardening

- [x] 5.1 Ensure the composer Input owns focus at launch via `AUTO_FOCUS` so the first `/` keystroke reaches the Input and triggers suggestions.
- [x] 5.2 Make the output `RichLog` non-focusable (`can_focus = False`) so it can never steal keyboard focus from the composer.
- [x] 5.3 Raise the suggestion panel and composer `max-height` so the full matched set (up to `_max_suggestions = 10`) is visible instead of clipped.
- [x] 5.4 Emit an audit event when the command registry fails to build so an empty suggestion list is observable rather than silent.


