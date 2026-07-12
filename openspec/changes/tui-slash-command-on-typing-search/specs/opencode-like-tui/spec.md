## MODIFIED Requirements

### Requirement: ComposerInput shall be the only user input surface

The composer SHALL accept natural-language questions and slash commands through the same input field,
and when the current input starts with `/`, the composer SHALL provide deterministic slash-command
discovery that updates while typing.

#### Scenario: User submits text

- **WHEN** the composer contains non-empty text
- **THEN** pressing Enter SHALL emit a submitted message containing the text
- **AND** SHALL clear the input
- **AND** SHALL route through the existing composer submission flow.

#### Scenario: Empty submission is ignored

- **WHEN** the composer contains only whitespace
- **AND** Enter is pressed
- **THEN** no route action SHALL run.

#### Scenario: Clear input behavior works

- **WHEN** the composer contains text
- **AND** Esc is pressed
- **THEN** the composer input SHALL be cleared.

#### Scenario: Slash mode opens suggestions

- **WHEN** the user types `/` as the first non-empty character
- **THEN** the composer SHALL display an available-command suggestion list.

#### Scenario: Slash mode filters suggestions while typing

- **WHEN** the user continues typing after `/`
- **THEN** the suggestion list SHALL only include command names with a case-insensitive prefix match
  against the typed text (after `/`).

#### Scenario: Suggestion list is hidden outside slash mode

- **WHEN** the composer input does not start with `/`
- **THEN** the slash-command suggestion list SHALL be hidden.

#### Scenario: Command route remains unchanged on Enter

- **WHEN** the user submits a command such as `/scan` from composer
- **THEN** routing SHALL continue to execute through the existing slash-command execution path.
