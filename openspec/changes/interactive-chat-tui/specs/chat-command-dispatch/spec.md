## ADDED Requirements

### Requirement: Chat input dispatches slash commands to CommandHandler
When the user types input starting with `/`, the `ChatPanel` SHALL parse the command name and arguments and dispatch to the existing `CommandHandler` pipeline, displaying the `CommandResult` inline in the chat log.

#### Scenario: Slash command dispatched
- **WHEN** the user types `/scan` and presses Enter
- **THEN** the input SHALL be routed to `CommandHandler` for `scan` with an empty args dict
- **AND** the `CommandResult` summary SHALL appear in the chat log

#### Scenario: Slash command with arguments
- **WHEN** the user types `/filter setup_type=BREAKOUT` and presses Enter
- **THEN** the filter args SHALL be parsed and passed to the filter `CommandHandler`
- **AND** the result SHALL appear in the chat log

#### Scenario: Unknown slash command
- **WHEN** the user types `/unknown_cmd`
- **THEN** the chat log SHALL show an error message listing valid commands

### Requirement: Non-slash input routes to the assistant
Any input that does NOT start with `/` SHALL be treated as a natural-language question and routed to `AssistantApp.ask()`.

#### Scenario: Free-form question routes to assistant
- **WHEN** the user types `show me the strongest candidates today`
- **THEN** the input SHALL be routed to `AssistantApp.ask()` and NOT to `CommandHandler`
