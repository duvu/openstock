## ADDED Requirements

### Requirement: ChatPanel is always visible at the bottom of the TUI
The TUI application SHALL render a `ChatPanel` widget persistently at the bottom of every screen, occupying approximately 30% of the terminal height. The panel SHALL remain visible and functional while any screen is active (watchlist, quality, outcomes, etc.).

#### Scenario: Chat panel visible on watchlist screen
- **WHEN** the user launches `vnalpha tui`
- **THEN** the watchlist SHALL be rendered in the upper portion of the terminal AND a chat input bar SHALL appear at the bottom

#### Scenario: Chat panel persists across screen navigation
- **WHEN** the user navigates from the watchlist screen to the quality screen (hotkey `p`)
- **THEN** the chat panel SHALL remain mounted at the bottom with its message history intact

#### Scenario: Toggle chat panel visibility
- **WHEN** the user presses `ctrl+\`
- **THEN** the chat panel SHALL toggle between visible and hidden states

### Requirement: Chat panel retains in-session message history
The `ChatPanel` SHALL maintain a scrollable log of all messages and tool-trace events for the current TUI session. History SHALL be cleared when the TUI application exits.

#### Scenario: History preserved across questions
- **WHEN** the user asks two successive questions in the same TUI session
- **THEN** both question/answer exchanges SHALL appear in the scrollable log in chronological order

#### Scenario: History cleared on exit
- **WHEN** the user quits the TUI (`q`) and relaunches
- **THEN** the chat log SHALL start empty

### Requirement: Chat input accepts natural-language questions
The `ChatPanel` input field SHALL accept free-form natural-language questions and route them to `AssistantApp.ask()`. The input SHALL be focused when the user presses `ctrl+/`.

#### Scenario: Ask a question
- **WHEN** the user types a question and presses Enter
- **THEN** the question SHALL appear in the chat log AND `AssistantApp.ask()` SHALL be invoked with that question
- **AND** the synthesized answer SHALL appear in the chat log when processing completes

#### Scenario: Input disabled during processing
- **WHEN** the user submits a question
- **THEN** the input field SHALL be disabled until the assistant response is received
