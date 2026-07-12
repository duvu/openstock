## Why

When the user types `/` in the TUI composer, the available slash commands are currently not shown. This makes command discovery impossible for users who do not already know the full command set and causes repeated back-and-forth for simple interactions.

The change is needed now because the TUI already accepts slash commands, but the discoverability gap is a major usability regression for a command-driven interface.

## What Changes

- Show a command suggestion list immediately when input starts with `/`.
- Implement on-typing filtering so the list narrows as the user enters the command prefix.
- Keep behavior consistent with existing command execution: Enter still runs the selected command, and no new command execution path is introduced.
- Add deterministic tests to verify suggestion rendering, filter logic, and selection behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `opencode-like-tui`: add slash-command autocomplete and on-typing search behavior to the composer command interaction flow so available commands are discoverable and selectable before submission.

## Impact

- Affects the TUI composer input layer and slash-command UX path in the `vnalpha` application.
- May require updates to command completion handlers, suggestion rendering widgets, and existing interaction tests in the TUI module.
- No API or data-provider surface changes; no external dependency additions expected.
