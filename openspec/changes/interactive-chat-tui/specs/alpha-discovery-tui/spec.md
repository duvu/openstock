## MODIFIED Requirements

### Requirement: vnalpha TUI application layout
The vnalpha TUI SHALL use a split-pane layout with the active research screen in the upper region and the `ChatPanel` in the lower region. The chat panel SHALL be mounted in `VnAlphaApp.compose()` and SHALL persist across all screen pushes and pops.

#### Scenario: Launch shows split layout
- **WHEN** the user runs `vnalpha tui`
- **THEN** the watchlist SHALL occupy the upper portion of the terminal AND the chat panel SHALL be visible at the bottom

#### Scenario: Screen navigation preserves chat state
- **WHEN** the user presses `w` (watchlist), then `p` (quality), then `w` again
- **THEN** the chat log content and input state SHALL be identical before and after the navigation
