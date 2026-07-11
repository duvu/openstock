# r4-chat-workspace Specification

## Purpose
TBD - created by archiving change r4-chat-workspace-100. Update Purpose after archive.
## Requirements
### Requirement: ChatPanel shall start with an active chat session

ChatPanel SHALL create or resume an active `chat_session` before constructing ChatController for normal TUI use.

#### Scenario: ChatPanel creates session on first mount

- **GIVEN** no active chat session exists for `surface='tui-chat'` and the target date
- **WHEN** ChatPanel is mounted inside VnAlphaApp
- **THEN** migrations SHALL run
- **AND** a new `chat_session` SHALL be created
- **AND** ChatController SHALL receive that `chat_session_id`.

#### Scenario: ChatPanel resumes latest active session

- **GIVEN** an active chat session exists for `surface='tui-chat'` and the target date
- **WHEN** ChatPanel starts
- **THEN** it SHALL resume the latest matching active session
- **AND** SHALL NOT create a duplicate session unless the user starts a new chat.

#### Scenario: Target date is stored in session

- **GIVEN** ChatPanel starts with target date `D`
- **WHEN** the chat session is created
- **THEN** the `chat_session.target_date` field SHALL equal `D`.

---

### Requirement: ChatController shall own all chat transcript persistence

ChatController SHALL persist chat audit rows through the same methods used by the TUI runtime path.

#### Scenario: User prompt is persisted

- **GIVEN** ChatController has an active `chat_session_id`
- **WHEN** a natural-language prompt is submitted
- **THEN** a `chat_message` row SHALL be written with role `user`
- **AND** content SHALL contain the submitted prompt.

#### Scenario: Assistant answer is persisted

- **GIVEN** ChatController receives an assistant answer
- **WHEN** the answer is rendered to the UI
- **THEN** a `chat_message` row SHALL be written with role `assistant`
- **AND** message type SHALL identify it as an answer.

#### Scenario: Assistant refusal is persisted

- **GIVEN** ChatController receives a refusal
- **WHEN** the refusal is rendered to the UI
- **THEN** a `chat_message` row SHALL be written with role `assistant`
- **AND** message type SHALL identify it as a refusal.

#### Scenario: Runtime error is persisted

- **GIVEN** a controller turn fails at runtime
- **WHEN** the error is rendered to the UI
- **THEN** an error row SHALL be persisted for the active chat session.

---

### Requirement: Command turns shall be persisted through the controller

Slash command input, command result, chat-local input, and chat-local output SHALL be persisted by ChatController.

#### Scenario: Slash input is persisted before command handling

- **GIVEN** an active chat session
- **WHEN** the user submits a research slash command
- **THEN** ChatController SHALL persist the raw slash input as a user command message before command handling.

#### Scenario: Slash command result is persisted

- **GIVEN** command handling returns a result
- **WHEN** ChatController renders that result
- **THEN** ChatController SHALL persist a result message
- **AND** SHALL include a research session reference when available.

#### Scenario: Chat-local input and output are persisted

- **GIVEN** an active chat session
- **WHEN** the user submits `/help`, `/context`, `/plan`, `/trace`, `/clear`, or `/new`
- **THEN** ChatController SHALL persist the local command input
- **AND** persist the local command output when one is produced.

---

### Requirement: Session lifecycle commands shall preserve transcript integrity

Session commands SHALL be deterministic and auditable.

#### Scenario: New chat creates a new session

- **GIVEN** ChatController has an active session
- **WHEN** the user starts a new chat
- **THEN** a new `chat_session` SHALL be created
- **AND** ChatController SHALL switch to the new session id
- **AND** pending plan state SHALL be cleared.

#### Scenario: Previous transcript remains queryable after new session

- **GIVEN** messages exist in session A
- **WHEN** the user starts session B and submits new messages
- **THEN** messages from session A SHALL remain queryable.

---

### Requirement: Clear command shall preserve transcript by default

`/clear` SHALL hide visible rows by default, not delete them.

#### Scenario: Clear hides visible rows

- **GIVEN** an active session contains visible chat messages
- **WHEN** the user submits `/clear`
- **THEN** visible messages SHALL be marked not visible
- **AND** `hidden_at` SHALL be set.

#### Scenario: Clear preserves audit rows

- **GIVEN** an active session contains persisted rows
- **WHEN** the user submits `/clear`
- **THEN** rows SHALL remain in `chat_message`
- **AND** SHALL be available when listing with hidden messages included.

#### Scenario: Destructive clear requires explicit flag

- **GIVEN** an active session contains persisted rows
- **WHEN** the user submits `/clear --forget`
- **THEN** rows MAY be deleted
- **BUT** deletion SHALL NOT occur without the explicit flag.

---

### Requirement: Plan lifecycle shall be auditable

Plan previews, approvals, cancellations, and final outcomes SHALL be persisted when a chat session is active.

#### Scenario: Plan preview is persisted

- **GIVEN** ChatController produces a plan preview
- **WHEN** the preview is shown to the user
- **THEN** a `chat_message` row SHALL be persisted with message type `plan_preview`
- **AND** `plan_json` SHALL contain the serialized plan.

#### Scenario: Plan approval is persisted

- **GIVEN** a pending plan exists
- **WHEN** the user approves the plan
- **THEN** a `plan_approval` row SHALL be persisted
- **AND** the final outcome SHALL also be persisted.

#### Scenario: Plan cancellation is persisted

- **GIVEN** a pending plan exists
- **WHEN** the user cancels the plan
- **THEN** a `plan_cancel` row SHALL be persisted
- **AND** pending plan state SHALL be cleared.

#### Scenario: Approval without pending plan does not create false audit row

- **GIVEN** no pending plan exists
- **WHEN** approval is requested
- **THEN** ChatController SHALL NOT persist a fake approval row.

---

### Requirement: Plan eligibility shall be checked before pending and before approval

ChatController SHALL check plan eligibility before a plan is stored as pending and again before approval continues.

#### Scenario: Eligible plan can proceed

- **GIVEN** a plan is eligible for the current mode
- **WHEN** ChatController handles the prompt
- **THEN** the plan MAY proceed according to the configured mode
- **AND** transcript rows SHALL be persisted.

#### Scenario: Ineligible plan is not pending

- **GIVEN** a plan is not eligible for R4 chat workspace
- **WHEN** ChatController reviews the plan
- **THEN** the plan SHALL be refused
- **AND** SHALL NOT be stored as pending
- **AND** the refusal SHALL be persisted.

#### Scenario: Pending plan is checked again on approval

- **GIVEN** a pending plan exists
- **WHEN** the user approves it
- **THEN** ChatController SHALL check eligibility again before continuing
- **AND** SHALL refuse and persist refusal if it is no longer eligible.

---

### Requirement: Trace timeline shall work for ChatPanel-created sessions

Trace persistence SHALL work in normal TUI ChatPanel use, not only in isolated controller tests.

#### Scenario: Trace callback persists event for active session

- **GIVEN** ChatPanel created or resumed a session
- **WHEN** a trace callback receives an event
- **THEN** the event SHALL be persisted for the active session.

#### Scenario: Trace command reads active session events

- **GIVEN** trace events exist for the active session
- **WHEN** the user submits `/trace`
- **THEN** ChatController SHALL return the persisted events in chronological order.

#### Scenario: Trace command handles no events

- **GIVEN** no trace events exist for the active session
- **WHEN** the user submits `/trace`
- **THEN** ChatController SHALL return a useful no-events message.

---

### Requirement: R4 verification target shall gate completion

The repository SHALL include a focused verification target for R4.

#### Scenario: R4 verification target runs all R4 tests

- **GIVEN** development dependencies are installed
- **WHEN** `make verify-r4` runs
- **THEN** it SHALL run ChatPanel tests
- **AND** controller-level persistence tests
- **AND** clear behavior tests
- **AND** permission/eligibility tests
- **AND** session lifecycle tests
- **AND** trace tests
- **AND** return non-zero if any required R4 test fails.

#### Scenario: Validation report records R4 result

- **GIVEN** `make verify-r4` has been run
- **WHEN** the validation report is updated
- **THEN** it SHALL include exact command output summary
- **AND** SHALL record failures or skipped tests honestly.

---

### Requirement: R4 documentation shall not overclaim

R4 documentation SHALL match actual implementation evidence.

#### Scenario: Completion matrix marks R4 as 100 only with evidence

- **GIVEN** all R4 implementation and validation tasks are complete
- **WHEN** the completion matrix is updated
- **THEN** R4 MAY be marked `100% POC-complete`
- **AND** the row SHALL cite implementation, controller-level tests, TUI tests, eligibility tests, trace tests, and validation report evidence.

#### Scenario: Open blockers prevent 100 percent claim

- **GIVEN** any R4 blocker remains open
- **WHEN** the completion matrix is updated
- **THEN** R4 SHALL NOT be marked 100%.

